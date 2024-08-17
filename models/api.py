from enum import Enum


class ApiModels(Enum):
    GPT4 = "gpt-4-0613"
    GPT4o = "gpt-4o-2024-08-06"
    GPT4_T = "gpt-4-1106-preview"
    GPT3_5 = "gpt-3.5-turbo-0613"


class ApiVoices(Enum):
    ECHO = "echo"
    NOVA = "nova"
    FABLE = "fable"
    ONYX = "onyx"
    ALLOY = "alloy"
    SHIMMER = "shimmer"
