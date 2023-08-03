from __future__ import annotations


from dataclasses import dataclass, field, asdict
import json
import random
from typing import DefaultDict, Dict, List, Tuple
from completion_api import ApiModels
from logger import Logger
from halo import Halo


import openai
from speech import listen, speak
from utils import get_generic_order_waiting_phrases, halo_context


@dataclass
class AbstractOrderData:
    def __repr__(self):
        return json.dumps(self.as_dict(), indent=4)

    def __str__(self):
        return self.__repr__()

    def as_dict(self):
        raise NotImplementedError

    @classmethod
    def get_schema(cls):
        raise NotImplementedError

    @classmethod
    def from_api_response(cls, response, **kwargs) -> AbstractOrderData:
        reply_content = response.choices[0].message
        string_order_kwargs = reply_content.to_dict()["function_call"]["arguments"]
        order_kwargs = json.loads(string_order_kwargs)
        cls_args = {**kwargs, **order_kwargs}
        return cls(**cls_args)


@dataclass
class AbstractAgent:
    api_model: str = field(init=False, default=ApiModels.GPT4.value)
    message_history: List[Dict] = field(init=False, default_factory=list)

    @Halo(spinner="dots", color="green", text="Thinking...")
    def get_function_completion_response(
        self, prompt: str, fn_name: str = None, with_message_history=False, **api_kwargs
    ):
        messages = [
            self.get_system_message(),
            *(self.message_history if with_message_history else []),
            {"role": "user", "content": prompt},
        ]
        if with_message_history:
            messages.extend(self.message_history)

        completion = openai.ChatCompletion.create(
            model=self.api_model,
            messages=messages,
            functions=[self.functions[fn_name]] if fn_name else None,
            function_call={"name": fn_name},
            **api_kwargs,
        )
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

    def communicate(
        self,
        msg: str,
        get_response=False,
        display_summary: str = "",
        speech_summary: str = "",
    ) -> str | None:
        with halo_context(spinner="dots", color="red") as spinner:

            def listen_for() -> str:
                err_msg = "Sorry, I did not get that. Can you please repeat it?"
                if self.speak:
                    response = listen(self.logger)
                    while not response:
                        print(err_msg + "\n\n")
                        speak(err_msg)
                        response = listen(self.logger)

                else:
                    spinner.stop()
                    while True:
                        response = input("waiting for response... \n\n")
                        if response:  # if the user entered something
                            break  # exit the loop
                        else:
                            input(err_msg)

                return response

            print(msg + display_summary + "\n\n")
            speak(msg + speech_summary)

            self.add_agent_message(msg)
            if get_response:
                user_response = listen_for()
                self.logger.info(f"user response: {user_response}")
                self.add_user_message(user_response)
                return user_response

    def waiting_for_api_response(self):
        self.communicate(f"\n {random.choice(get_generic_order_waiting_phrases())} \n")
