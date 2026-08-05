from faker import Faker
import random
import string
from datetime import datetime
"""
数据模拟工具
"""

class FakerData:
    def __init__(self, locale: str = "zh_CN"):
        self.fake = Faker(locale)
        Faker.seed(0)

    # 随机用户名:前缀+月日时分秒+6位随机字符，保证高并发下不冲突
    def random_username(self, pre: str = "user", length: int = 14) -> str:
        timestamp = datetime.now().strftime('%m%d%H%M%S')
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        combined = f"{pre}{timestamp}{rand_suffix}"
        return combined[:length]

    def random_email(self) -> str:
        return self.fake.email()

    def random_phone(self) -> str:
        return self.fake.phone_number()

    def random_name(self, pre: str = "org", max_length: int = 20) -> str:
        timestamp = datetime.now().strftime('%m%d%H%M%S')
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        combined = f"{pre}_{timestamp}{rand_suffix}"
        return combined[:max_length]

    def random_nickname(self) -> str:
        return self.fake.user_name()

    def random_password(self, length: int = 12) -> str:
        chars = string.ascii_letters + string.digits + string.punctuation
        return ''.join(random.choice(chars) for _ in range(length))

    def random_int(self, min_val: int = 0, max_val: int = 100) -> int:
        return self.fake.random_int(min=min_val, max=max_val)

    def random_float(self, min_val: float = 0.0, max_val: float = 100.0) -> float:
        return round(self.fake.random_float(min=min_val, max=max_val), 2)

    def random_date(self) -> str:
        return self.fake.date().strftime("%Y-%m-%d")

    def random_datetime(self) -> str:
        return self.fake.date_time().strftime("%Y-%m-%d %H:%M:%S")

    def random_str(self, length: int = 10) -> str:
        return self.fake.pystr(min_chars=length, max_chars=length)

    def random_list(self, count: int = 5, item_type: str = "str") -> list:
        result = []
        for _ in range(count):
            if item_type == "int":
                result.append(self.random_int())
            elif item_type == "float":
                result.append(self.random_float())
            else:
                result.append(self.random_str())
        return result

    def random_dict(self, keys: list = None) -> dict:
        if keys is None:
            keys = ["name", "value", "code"]
        return {key: self.random_str() for key in keys}

    # 随机句子
    def random_sentence(self, length: int = 50) -> str:
        return self.fake.sentence(nb_words=length) 
    
    def generate_user_data(self) -> dict:
        return {
            "username": self.random_username(),
            "email": self.random_email(),
            "phone": self.random_phone(),
            "name": self.random_name(pre="user"),
            "nickname": self.random_nickname(),
            "password": self.random_password()
        }


faker_data = FakerData()
