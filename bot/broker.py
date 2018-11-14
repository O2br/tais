import logging
import os
import time
import datetime
import hashlib
import json

from rasa_core.broker import EventChannel
from rasa_core.events import ActionExecuted, BotUttered, UserUttered

from elasticsearch import Elasticsearch
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)

ENVIRONMENT_NAME = os.getenv('ENVIRONMENT_NAME', 'locahost')
BOT_VERSION = os.getenv('BOT_VERSION', 'notdefined')
HASH_GEN = hashlib.md5()

def gen_id(timestamp):
    HASH_GEN.update(str(timestamp).encode('utf-8'))
    _id = HASH_GEN.hexdigest()[10:]
    return _id

class ElasticSearchBroker(EventChannel):
    def __init__(self, host, username=None, password=None):
        # TODO http auth
        self.es = Elasticsearch([host])

    def publish(self, event):
        if 'timestamp' in event:
            event['timestamp'] = datetime.datetime.strftime(
                datetime.datetime.fromtimestamp(event['timestamp']),
                '%Y/%m/%d %H:%M:%S'
            )
        logger.debug('='*80)
        logger.debug(event)
        # try:
        #     self.save_user_message(tracker)
        #     self.save_bot_message(tracker)
        # except Exception as ex:
        #     logger.error('Could not track messages '
        #                  'for user {}'.format(tracker.sender_id))
        #     logger.error(str(ex))

    def save_user_message(self, tracker):
        if not tracker.latest_message.text:
            return

        ts = time.time()
        timestamp = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(ts),
            '%Y/%m/%d %H:%M:%S'
        )

        #Bag of words
        tags = []
        for word in tracker.latest_message.text.replace('. ',' ').replace(',',' ').replace('"','').replace("'",'').replace('*','').replace('(','').replace(')','').split(' '):
            if word.lower() not in stopwords.words('portuguese') and len(word) > 1:
                tags.append(word)

        message = {
            'environment': ENVIRONMENT_NAME,
            'version': BOT_VERSION,

            'user_id': tracker.sender_id,
            'is_bot': False,
            'timestamp': timestamp,

            'text': tracker.latest_message.text,
            'tags': tags,

            'entities': tracker.latest_message.entities,
            'intent_name': tracker.latest_message.intent['name'],
            'intent_confidence': tracker.latest_message.intent['confidence'],

            'utter_name': '',
            'is_fallback': False,
        }

        self.es.index(index='messages', doc_type='message',
                 id='{}_user_{}'.format(ENVIRONMENT_NAME, gen_id(ts)),
                 body=json.dumps(message))

    def save_bot_message(self, tracker):
        if not tracker.latest_message.text:
            return

        utters = []
        index = len(tracker.events) - 1
        while True:
            evt = tracker.events[index]
            if isinstance(evt, UserUttered):
                break
            elif isinstance(evt, BotUttered):
                while not isinstance(evt, ActionExecuted):
                    index -= 1
                    evt = tracker.events[index]
                utters.append(evt.action_name)
            index -= 1


        time_offset = 0
        for utter in utters[::-1]:
            time_offset += 100

            ts = (
                datetime.datetime.now() +
                datetime.timedelta(milliseconds=time_offset)
            ).timestamp()

            timestamp = datetime.datetime.strftime(
                datetime.datetime.fromtimestamp(ts),
                '%Y/%m/%d %H:%M:%S'
            )

            message = {
                'environment': ENVIRONMENT_NAME,
                'version': BOT_VERSION,
                'user_id': tracker.sender_id,

                'is_bot': True,

                'text': '',
                'tags': [],
                'timestamp': timestamp,

                'entities': [],
                'intent_name': '',
                'intent_confidence': '',

                'utter_name': utter,
                'is_fallback': utter == 'action_default_fallback',
            }

            self.es.index(index='messages', doc_type='message',
                     id='{}_bot_{}'.format(ENVIRONMENT_NAME, gen_id(ts)),
                     body=json.dumps(message))
