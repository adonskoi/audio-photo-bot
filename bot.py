import logging


import requests
import telebot
from pydub import AudioSegment
from pymongo import MongoClient
import face_recognition

from config import DB, TOKEN

client = MongoClient(DB)
db = client.bot_db

logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["get_files"])
def get_list_of_files_contoller(message):
    """send list of user files"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    if db.files.count_documents({"user_id": user_id}) > 0:
        list_ = db.files.find({"user_id": user_id})
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for file in list_:
            markup.add(
                telebot.types.KeyboardButton(
                    text=f'/get_file {file["id"]} {file["type"]}'
                )
            )
        text = "Please choose file:"
        bot.reply_to(message, text, reply_markup=markup)
    else:
        text = "Files not found"
        bot.reply_to(message, text)


@bot.message_handler(commands=["get_file"])
def get_file_contoller(message):
    """send file by id"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        id = message.text.split(" ")[1]
        file = db.files.find_one({"user_id": user_id, "id": int(id)})
        if file is not None:
            file_path = file["path"]
            with open(file_path, "rb") as content:
                if file["type"] == "photo":
                    bot.send_photo(chat_id, content)
                if file["type"] == "audio":
                    bot.send_audio(chat_id, content)
                else:
                    bot.send_voice(chat_id, content)
        else:
            text = "File not found"
            bot.reply_to(message, text)
    except IndexError:
        text = "Please specify file id"
        bot.reply_to(message, text)


@bot.message_handler(content_types=["audio"])
def save_voice_files(message):
    file_id = message.audio.file_id
    user_id = message.from_user.id
    date = message.date
    id = save_audio_file(file_id, user_id, date)
    bot.reply_to(message, f"ок: {id}")


@bot.message_handler(content_types=["voice"])
def save_voice_files(message):
    file_id = message.voice.file_id
    user_id = message.from_user.id
    date = message.date
    id = save_voice_file(file_id, user_id, date)
    bot.reply_to(message, f"ок: {id}")


@bot.message_handler(content_types=["photo"])
def save_photo(message):
    user_id = message.from_user.id
    print(message.photo[0])
    date = message.date
    file_id = message.photo[0].file_id
    id, faces_count = check_and_save_photo(file_id, user_id, date)
    if faces_count > 0:
        bot.reply_to(message, f"ок: {id},faces: {faces_count}")
    else:
        bot.reply_to(message, "no faces on photo")


def save_voice_file(file_id, user_id, date):
    file_info = bot.get_file(file_id)
    response = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
    )
    path = "uploads/" + file_id + ".wav"
    with open("temp", "w+b") as output:
        output.write(response.content)
        ogg_file = AudioSegment.from_ogg("temp")
        ogg_file.set_frame_rate(16000).export(path, format="wav")
    count = db.files.count_documents({"user_id": user_id})
    data = {
        "id": count + 1,
        "path": path,
        "user_id": user_id,
        "date": date,
        "type": "voice",
    }
    result = db.files.insert_one(data)
    return data["id"]


def save_audio_file(file_id, user_id, date):
    file_info = bot.get_file(file_id)
    response = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
    )
    path = "uploads/" + file_id + ".wav"
    with open("temp", "w+b") as output:
        output.write(response.content)
        ogg_file = AudioSegment.from_mp3("temp")
        ogg_file.set_frame_rate(16000).export(path, format="wav")
    count = db.files.count_documents({"user_id": user_id})
    data = {
        "id": count + 1,
        "path": path,
        "user_id": user_id,
        "date": date,
        "type": "audio",
    }
    result = db.files.insert_one(data)
    return data["id"]


def check_and_save_photo(file_id, user_id, date):
    file_info = bot.get_file(file_id)
    # add to path from file_info
    response = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
    )
    path = "uploads/" + file_id
    with open(path, "w+b") as output:
        output.write(response.content)
        image = face_recognition.load_image_file(path)
        face_locations = face_recognition.face_locations(image)
    if len(face_locations) > 0:
        count = db.files.count_documents({"user_id": user_id})
        data = {
            "id": count + 1,
            "path": path,
            "user_id": user_id,
            "date": date,
            "type": "photo",
        }
        result = db.files.insert_one(data)
        return data["id"], len(face_locations)
    else:
        return 0, 0


bot.polling()
