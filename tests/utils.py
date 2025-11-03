from types import SimpleNamespace
from typing import List, Tuple, Dict, Any


class FakeBot:
    def __init__(self):
        self.sent_messages: List[Tuple[int, str, Dict]] = []
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))
    
    def get_message_to(self, chat_id: int) -> List[str]:
        return [msg[1] for msg in self.sent_messages if msg[0] == chat_id]
    
    def clear(self):
        self.sent_messages = []


class FakeDispatcher:
    def __init__(self):
        self.message_handlers = {}
        self.callback_handlers = {}

    def message(self, *filters, **kwargs):
        def decorator(handler):
            self.message_handlers[handler.__name__] = handler
            return handler

        return decorator

    def callback_query(self, *filters, **kwargs):
        def decorator(handler):
            self.callback_handlers[handler.__name__] = handler
            return handler

        return decorator


class FakeFSMContext:
    def __init__(self):
        self.state = None
        self.data = {}
        self.cleared = False

    async def set_state(self, value):
        self.state = value

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.state = None
        self.data = {}
        self.cleared = True


class FakeMessage:
    def __init__(self, user_id, text="", username=None, first_name=None, last_name=None):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, username=username, first_name=first_name, last_name=last_name)
        self.answers: List[Tuple[str, Dict]] = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
    
    def get_last_answer_text(self) -> str:
        return self.answers[-1][0] if self.answers else ""
    
    def get_all_answers(self) -> List[str]:
        return [answer[0] for answer in self.answers]


class FakeCallbackMessage:
    def __init__(self, text=""):
        self.text = text
        self.edits: List[Tuple[str, Dict]] = []

    async def edit_text(self, text, **kwargs):
        self.edits.append((text, kwargs))
    
    def get_last_edit_text(self) -> str:
        return self.edits[-1][0] if self.edits else ""


class FakeCallbackQuery:
    def __init__(self, user_id, data, message: FakeCallbackMessage):
        self.from_user = SimpleNamespace(id=user_id)
        self.data = data
        self.message = message
        self.answers: List[Tuple[str, Dict]] = []

    async def answer(self, text="", **kwargs):
        self.answers.append((text, kwargs))
    
    def get_last_answer_text(self) -> str:
        return self.answers[-1][0] if self.answers else ""


def create_fake_message(user_id: int, text: str = "", **user_attrs) -> FakeMessage:
    return FakeMessage(
        user_id=user_id,
        text=text,
        username=user_attrs.get('username'),
        first_name=user_attrs.get('first_name'),
        last_name=user_attrs.get('last_name')
    )


def create_fake_callback(user_id: int, data: str, message_text: str = "") -> FakeCallbackQuery:
    message = FakeCallbackMessage(text=message_text)
    return FakeCallbackQuery(user_id=user_id, data=data, message=message)

