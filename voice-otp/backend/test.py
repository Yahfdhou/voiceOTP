from otp.generator import generate_otp, store_otp, verify_otp


code = generate_otp()
print("الكود المولّد:", code)
store_otp("user1", code)

# جرب التحقق
ok, reason = verify_otp("user1", code)
print(ok, reason)  # لازم يطبع True ok
