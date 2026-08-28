# Voice OTP - Run et Test

## Prerequis

- Python 3 installe
- Dependances backend installees (Flask, redis)
- Redis en execution si tu veux le stockage Redis

## 1) Aller dans le bon dossier

Depuis PowerShell:

```powershell
cd D:\voice-otpbackendotp\voice-otp\backend
```

## 2) Lancer le serveur Flask

```powershell
python app.py
```

Resultat attendu:

```text
* Running on http://127.0.0.1:5000
```

Laisse ce terminal ouvert.

## 3) Tester la demande OTP (nouveau terminal)

Ouvre un deuxieme terminal PowerShell, puis execute:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/auth/request-voice-otp -Method POST -ContentType "application/json" -Body '{"userId":"user1","phoneNumber":"+22245123456"}'
```

Resultat attendu:

```text
status : sent
```

Dans le terminal du serveur, tu verras une ligne simulation avec le code OTP.

## 4) Verifier le code OTP

Remplace XXXXXX par le code vu dans la simulation:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/auth/verify-otp -Method POST -ContentType "application/json" -Body '{"userId":"user1","otp":"XXXXXX"}'
```

Resultat attendu:

```text
ok : True
```

## 5) Erreurs frequentes

- invalid: OTP incorrect (souvent espace avant/apres le code)
- expired: OTP expire
- OTP est a usage unique: un code valide ne marche qu une seule fois



Invoke-RestMethod -Uri "http://127.0.0.1:5000/auth/request-voice-otp" -Method POST -ContentType "application/json" -Body '{"userId":"user1","phoneNumber":"+22245123456"}'

----------------------------

cd D:\voice-otpbackendotp\voice-otp\backend
python app.py
Terminal 2 — frontend React

PowerShell :

cd D:\voice-otpbackendotp\voice-otp\frontend
npm.cmd run dev
CMD :

cd D:\voice-otpbackendotp\voice-otp\frontend
npm run dev
Puis ouvre : http://localhost:5173 (ou 5174 si 5173 est déjà pris).
------------------------------------------------------------------