import contextlib
from typing import List

from halo import Halo


@contextlib.contextmanager
def halo_context(*args, **kwargs):
    spinner = Halo(*args, **kwargs)
    spinner.start()
    try:
        yield spinner
    finally:
        spinner.stop()


def get_generic_order_waiting_phrases() -> List[str]:
    return [
        "One moment please...",
        "Just a second, please...",
        "Bear with me for a moment...",
        "Please hold on a bit...",
        "Allow me a moment, please...",
        "Give me a short while...",
        "Could you wait a moment, please...",
        "Let me check that for you...",
        "Hang on for a sec, please...",
        "A moment to sort this out, please...",
        "Stand by for a minute, please...",
        "Please be patient for a moment...",
        "Just a minute, if you could...",
        "Please give me a moment...",
        "Hold on just a moment...",
        "Allow me a sec to verify that...",
        "I'll be right with you...",
        "Kindly wait a moment...",
        "Please hold on for a moment...",
        "Could you hold on for a sec?...",
        "One brief moment, please...",
        "Please give me a sec...",
        "Please stand by a moment...",
        "Allow me a brief moment...",
        "Could you spare a moment?...",
        "Just need a second, please...",
    ]


def get_generic_requests_to_repeat_order() -> List[str]:
    return [
        "Sorry, I didn't catch that. Could you say it again, please?",
        "I'm not sure I understood. Could you repeat that?",
        "Pardon me, can you please restate that?",
        "I didn't quite get that. Would you mind repeating?",
        "Can you please clarify what you just said?",
        "My apologies, but I didn't understand. Can you say that one more time?",
        "Could you please repeat that for clarification?",
        "I'm sorry, I missed that. Could you repeat it?",
        "I'm having trouble understanding. Could you say that again?",
        "Would you mind speaking that once more?",
        "I need a bit more clarity. Could you repeat, please?",
        "Apologies, but I didn't get that. Can you repeat?",
        "I didn't fully catch that. Can you say it again?",
        "Sorry, can you rephrase that for me?",
        "Could you please say that one more time?",
        "I'm not sure I caught that. Can you repeat?",
        "Could you kindly repeat what you just said?",
        "I'm sorry, could you say that again?",
        "I need to hear that once more. Could you repeat, please?",
        "My apologies, I didn't catch that. Can you restate it?",
        "I'm having a bit of trouble understanding. Can you repeat that?",
        "Sorry, I need you to say that again.",
        "I didn't quite catch that. Could you please repeat?",
        "Can you please go over that one more time?",
        "I'm sorry, I didn't hear that clearly. Can you say it again?",
        "Sorry, I missed what you just said. Can you repeat it?",
        "Can you say that once more, please?",
        "I didn't get that clearly. Can you repeat it?",
        "Could you please elaborate on that once more?",
        "I'm sorry, can you express that again?",
        "Could you please repeat your last statement?",
        "I'm having trouble catching that. Can you repeat?",
        "Sorry, can you say that one more time?",
        "I need to make sure I understood. Can you repeat that?",
        "I'm not certain I got that. Could you repeat it, please?",
        "I'm sorry, I need you to say that again.",
        "I didn't quite understand that. Could you please repeat?",
        "I need clarification on that. Could you repeat, please?",
        "I missed that, sorry. Can you say it again?",
        "I'm sorry, can you repeat what you just said?",
        "I need a little more detail. Can you say that again?",
        "I'm not sure I heard you right. Can you repeat that?",
        "Could you please say that again for me?",
        "I didn't catch that last part. Can you repeat?",
        "I need you to repeat that, please.",
        "I'm sorry, I didn't get your meaning. Can you say that again?",
        "Could you please repeat your previous comment?",
        "Sorry, I need that information again. Can you repeat it?",
        "I didn't catch that clearly. Can you say it again?",
        "I'm sorry, could you go over that once more?",
        "I need you to say that again, please.",
        "I didn't quite get your point. Could you repeat it?",
        "Could you please repeat that for me?",
        "Sorry, I missed that. Can you say it again?",
        "I'm sorry, can you clarify that once more?",
        "I didn't understand that. Could you say it again?",
        "I need to hear that again. Can you repeat it, please?",
        "Sorry, I need a bit more clarity. Can you repeat that?",
        "I didn't catch your last statement. Could you repeat it?",
        "Can you please go over that one more time for me?",
    ]
