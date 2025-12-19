from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

# Cấu hình bảo mật
SECRET_KEY = "day_la_khoa_bi_mat_sieu_cuc_ky_bao_mat_cua_cau_nha"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- SỬA DÒNG DƯỚI ĐÂY ---
# Đổi từ ["bcrypt"] sang ["pbkdf2_sha256"] để tránh lỗi trên Windows
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt