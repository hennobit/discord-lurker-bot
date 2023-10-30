from datetime import datetime
from enums import MicState
import logger


def get_mic_state(member) -> str:
    if member.voice is None:
        return ''

    if member.voice.self_deaf:
        return MicState.SOUND_MUTED.value

    if member.voice.self_mute:
        return MicState.MUTED.value

    return MicState.UNMUTED.value

def date_string_to_date(time_str: str) -> datetime:
    # issue #6. occurred one time. I don't know why and I couldn't recreate it
    try:
        # try to use the format with microseconds
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        try:
            # if that fails, try to use the format without microseconds
            logger.bot_logger.error('Failed to parse date string with microseconds. Trying without microseconds... time_str: ' + time_str)
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # if that fails, return None
            return None