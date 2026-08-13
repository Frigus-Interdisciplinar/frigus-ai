from pymongo import MongoClient
from pymongo.database import Database

from config.settings import settings


def _conectar() -> Database:

    cliente = MongoClient(settings.MONGODB_URI)
    return cliente["frigus_ai"]


banco = _conectar()
