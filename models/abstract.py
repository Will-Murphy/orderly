from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import asdict, dataclass, field
from functools import wraps
from typing import Dict, List, Tuple

from halo import Halo
from openai import OpenAI

from completion_api import ApiModels
from logger import Logger
from utils.speech import (
    adjust_for_ambient_noise,
    adjust_for_ambient_noise_async,
    listen,
    listen_new,
    speak,
    speak_new,
)
from utils.ux import (
    get_generic_order_waiting_phrases,
    get_generic_requests_to_repeat_order,
    halo_context,
)


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
        return cls(**cls_args)


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
    api_model: str = field(init=False, default=ApiModels.GPT4_T.value)
    message_history: List[Dict] = field(init=False, default_factory=list)
    usage_data: UsageData = field(init=False, default_factory=UsageData)

    def __post_init__(self, *args, **kwargs):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @Halo(spinner="dots", color="green", text="Thinking...")
    def get_func_completion_res(
        self, prompt: str, fn_name: str = None, with_message_history=False, **api_kwargs
    ):
        messages = [
            self.get_system_message(),
            *(self.message_history if with_message_history else []),
            {"role": "user", "content": prompt},
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
        waiting_res = asyncio.create_task(self.waiting_for_api_response())

        completion = await asyncio.to_thread(
            self.get_func_completion_res,
            *args,
            **kwargs,
        )

        await waiting_res

        return completion

    @property
    def functions(self):
        raise NotImplementedError

    @property
    def logger(self):
        raise NotImplementedError

    def get_system_message(self):
        raise NotImplementedError

    def get_listen_prompt(self):
        raise NotImplementedError

    def add_user_message(self, msg):
        self.message_history.append({"role": "user", "content": msg})

    def add_agent_message(self, msg):
        self.message_history.append({"role": "assistant", "content": msg})

    def communicate(
        self,
        msg: str = "",
        get_response=False,
        display_summary: str = "",
        speech_summary: str = "",
        add_to_message_history=True,
        with_ui_spinner=True,
    ) -> str | None:
        def listen_for(spinner=None) -> str:
            if self.speak:
                response = listen(self.logger)
                while not response:
                    err_msg = random.choice(get_generic_requests_to_repeat_order())
                    print(err_msg + "\n\n")
                    speak_new(self.client, err_msg)
                    response = listen(self.logger)

            else:
                if spinner:
                    spinner.stop()

                while True:
                    response = input("waiting for response... \n\n")
                    if response:  # if the user entered something
                        break  # exit the loop
                    else:
                        input(err_msg)

            return response

        def do_communication(spinner=None):
            if msg:
                print(msg + display_summary + "\n\n")
                speak_new(self.client, msg + speech_summary)

            if msg and add_to_message_history:
                self.add_agent_message(msg)
            if get_response:
                user_response = listen_for(spinner)
                self.logger.info(f"user response: {user_response}")
                if add_to_message_history:
                    self.add_user_message(user_response)
                return user_response

        if with_ui_spinner:
            with halo_context(spinner="dots", color="red") as spinner:
                return do_communication(spinner)
        else:
            return do_communication()

    async def communicate_async(self, *args, **kwargs):
        return self.communicate(*args, **kwargs)

    async def waiting_for_api_response(self):
        await self.communicate_async(
            f"\n {random.choice(get_generic_order_waiting_phrases())} \n",
            add_to_message_history=False,
            with_ui_spinner=False,
        )

    @staticmethod
    def calibrate_listening(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            async def adjust_for_ambient_noise_task():
                await adjust_for_ambient_noise_async()

            if self.speak:
                self.logger.debug("Adjusting for ambient noise...")
                asyncio.create_task(adjust_for_ambient_noise_task())

            result = await func(self, *args, **kwargs)
            return result

        return wrapper
