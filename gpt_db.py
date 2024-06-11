from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String)
    content = Column(String)
    date = Column(DateTime, default=datetime.datetime.utcnow)

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)

class ChatMessageLink(Base):
    __tablename__ = 'chat_message_links'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey('messages.id'))
    chat_id = Column(Integer, ForeignKey('chats.id'))
    message = relationship("Message")
    chat = relationship("Chat")

def add_chat(title):
    session = Session()
    new_chat = Chat(title=title)
    session.add(new_chat)
    session.commit()
    return new_chat.id

def add_message(chat_id, role, content):
    session = Session()
    new_message = Message(role=role, content=content)
    session.add(new_message)
    session.commit()
    chat_link = ChatMessageLink(message_id=new_message.id, chat_id=chat_id)
    session.add(chat_link)
    session.commit()

def get_all_messages(chat_id):
    session = Session()
    messages_query = session.query(Message).join(ChatMessageLink).filter(ChatMessageLink.chat_id == chat_id).order_by(Message.date).all()
    return [(msg.date, msg.role, msg.content) for msg in messages_query]

def get_recent_chats(chats_to_return):
    session = Session()
    recent_chats = session.query(Chat).order_by(Message.date.desc()).limit(chats_to_return).all()
    return recent_chats 

# Setup the database
database_path = os.path.expanduser('~/.gpt/chats.db')
if not os.path.exists(database_path):
    os.makedirs(os.path.dirname(database_path), exist_ok=True)

engine = create_engine('sqlite:///' + database_path)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
