from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import asdict, dataclass, field
from typing import Dict, List

from halo import Halo
from openai import OpenAI

from models.api import ApiModels, ApiVoices
from utils.speech import adjust_for_ambient_noise_async, listen, speak_new
from utils.ux import (
    get_generic_order_waiting_phrases,
    get_generic_requests_to_repeat_order,
    halo_context,
)

DEFAULT_MAX_NO_INPUT_RETRIES = 5
DEFAULT_MAX_API_RETRIES = 5

DEFAULT_API_MODEL = ApiModels.GPT4o.value
DEFAULT_API_VOICE = ApiVoices.ONYX.value


class ApiResponseException(Exception):
    pass


class NoInputException(Exception):
    pass


@dataclass
class AbstractOrderData:
    def __repr__(self):
        return json.dumps(self.as_dict(), indent=4)

    def __str__(self):
        return self.__repr__()

    def as_dict(self):
        return asdict(self)

    @classmethod
    def get_schema(cls):
        raise NotImplementedError

    @classmethod
    def from_api_response(cls, response, **kwargs) -> AbstractOrderData:
        reply_content = response.choices[0].message
        string_order_kwargs = reply_content.tool_calls[0].function.arguments
        order_kwargs = json.loads(string_order_kwargs)
        cls_args = {**kwargs, **order_kwargs}
        try:
            return cls(**cls_args)
        except TypeError as e:
            raise ApiResponseException("Unexpected API response format") from e


@dataclass
class UsageData:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add_usage(self, response):
        self.prompt_tokens += response.usage.prompt_tokens
        self.completion_tokens += response.usage.completion_tokens
        self.total_tokens += response.usage.total_tokens


@dataclass
class AbstractAgent:
    api_model: str = field(init=False, default=DEFAULT_API_MODEL)
    voice_selection: str = field(init=True, kw_only=True, default=DEFAULT_API_VOICE)
    message_history: List[Dict] = field(init=False, default_factory=list)
    usage_data: UsageData = field(init=False, default_factory=UsageData)
    max_no_input_retries: int = field(init=False, default=DEFAULT_MAX_NO_INPUT_RETRIES)

    def __post_init__(self, *args, **kwargs):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @Halo(spinner="hamburger", color="grey", text="Thinking...")
    def get_func_completion_res(
        self,
        add_user_msg: str = "",
        add_system_msg: str = "",
        fn_name: str = None,
        with_message_history=True,
        **api_kwargs,
    ):
        if add_system_msg:
            self.add_system_message(add_system_msg)
        if add_user_msg:
            self.add_user_message(add_user_msg)

        messages = [
            self.get_system_message(),
            *(self.message_history if with_message_history else []),
        ]

        self.logger.debug(f"For response messages: {json.dumps(messages,indent=4)}")

        function_as_tool = {"type": "function", "function": self.functions[fn_name]}

        function_call = {"type": "function", "function": {"name": fn_name}}

        completion = self.client.chat.completions.create(
            model=self.api_model,
            messages=messages,
            tools=[function_as_tool],
            tool_choice=function_call,
            **api_kwargs,
        )

        self.usage_data.add_usage(completion)

        return completion

    async def get_func_completion_res_with_waiting(self, *args, **kwargs):
        waiting_res = asyncio.create_task(self.waiting_for_api_response_task())

        noise_adjustment = asyncio.create_task(self.adjust_for_ambient_noise_task())

        completion = await asyncio.to_thread(
            self.get_func_completion_res,
            *args,
            **kwargs,
        )

        await waiting_res

        # cancel if not done to avoid slowing response
        if not noise_adjustment.done():
            noise_adjustment.cancel()

        await noise_adjustment

        return completion

    @property
    def functions(self):
        raise NotImplementedError

    @property
    def logger(self):
        raise NotImplementedError

    def get_system_message(self):
        raise NotImplementedError

    def add_user_message(self, msg):
        self.message_history.append({"role": "user", "content": msg})

    def add_agent_message(self, msg):
        self.message_history.append({"role": "assistant", "content": msg})

    def add_system_message(self, msg):
        self.message_history.append({"role": "system", "content": msg})

    def communicate(
        self,
        msg: str = "",
        get_response=False,
        display_summary: str = "",
        speech_summary: str = "",
        add_to_message_history=True,
        with_ui_spinner=True,
        speech_blocking=True,
    ) -> str | None:
        def listen_for(speaking_spinner) -> str:
            speaking_spinner.stop()

            with halo_context(
                spinner="hamburger", color="green", text="Listening..."
            ) as listening_spinner:
                if self.use_speech_input:
                    response = listen(self.logger)
                    no_input_retries = 0
                    while not response:
                        err_msg = random.choice(get_generic_requests_to_repeat_order())
                        print(err_msg + "\n\n")

                        listening_spinner.stop()
                        speaking_spinner.start()
                        speak_new(
                            self.client,
                            err_msg,
                            voice_selection=self.voice_selection,
                            blocking=speech_blocking,
                        )

                        speaking_spinner.stop()
                        listening_spinner.start()
                        response = listen(self.logger)

                        no_input_retries += 1
                        if no_input_retries >= self.max_no_input_retries:
                            raise NoInputException(
                                "No input detected after max retries"
                            )
                else:
                    if listening_spinner:
                        listening_spinner.stop()

                    while True:
                        response = input("waiting for response... \n\n")
                        if response:  # if the user entered something
                            break  # exit the loop
                        else:
                            input(err_msg)

                return response

        with halo_context(
            spinner="hamburger",
            color="red",
            text="Speaking...",
            enabled=with_ui_spinner,
        ) as speaking_spinner:
            if msg:
                print(msg + display_summary + "\n\n")
                speak_new(
                    self.client,
                    msg + speech_summary,
                    voice_selection=self.voice_selection,
                    blocking=speech_blocking,
                )

            if msg and add_to_message_history:
                self.add_agent_message(msg)
            if get_response:
                user_response = listen_for(speaking_spinner)
                self.logger.info(f"user response: {user_response}")
                return user_response

    async def communicate_async(self, *args, **kwargs):
        return self.communicate(*args, **kwargs)

    async def waiting_for_api_response_task(self):
        await self.communicate_async(
            f"\n {random.choice(get_generic_order_waiting_phrases())} \n",
            add_to_message_history=False,
            with_ui_spinner=False,
            speech_blocking=False,
        )

    async def adjust_for_ambient_noise_task(self):
        try:
            await adjust_for_ambient_noise_async()
            self.logger.debug("Ambient noise adjustment done...")
        except asyncio.CancelledError:
            self.logger.debug("Ambient noise adjustment cancelled...")
