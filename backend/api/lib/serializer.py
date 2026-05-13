from itsdangerous import URLSafeSerializer
from config.Config import *
config = Config()
serializer = URLSafeSerializer(config.ItsDangerousKey)
