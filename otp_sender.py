def send_code(phone: str, code: str) -> None:
    # PLUG: no futuro troca por Twilio/Zenvia/WhatsApp Cloud API etc.
    print(f"[DEV OTP] Código para {phone}: {code}")