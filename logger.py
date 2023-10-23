import logging

#  Bot Logger
bot_logger = logging.getLogger('Bot')
bot_handler = logging.FileHandler('bot.log', encoding='utf-8')
bot_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
bot_handler.setFormatter(bot_formatter)
bot_logger.addHandler(bot_handler)
bot_logger.setLevel(logging.DEBUG)

