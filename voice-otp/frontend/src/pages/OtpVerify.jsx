import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleAlert, LoaderCircle, Mail, MessageSquare, Send } from "lucide-react";
import { COUNTRIES } from "../countries.js";
import Shell from "../components/Shell.jsx";

const API_BASE = "http://127.0.0.1:5000";

const COPY = {
  sms: {
    collectTitle: "Numéro SMS",
    collectHint: "Choisissez l'indicatif, puis saisissez votre numéro.",
    sendingTitle: "Envoi du SMS...",
    submit: "Envoyer le SMS",
  },
  email: {
    collectTitle: "Votre e-mail",
    collectHint: "Entrez votre adresse. Le code sera envoyé uniquement là.",
    sendingTitle: "Envoi du code...",
    submit: "Recevoir le code",
  },
};

export default function OtpVerify({ channel }) {
  const navigate = useNavigate();
  const copy = COPY[channel];
  const userId = localStorage.getItem("userId");

  const [phase, setPhase] = useState("collect");
  const [countries] = useState(COUNTRIES);
  const [countryCode, setCountryCode] = useState(
    () => localStorage.getItem("countryCode") || "+222"
  );
  const [nationalNumber, setNationalNumber] = useState(
    () => localStorage.getItem("nationalNumber") || ""
  );
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  const selected = useMemo(
    () => countries.find((c) => c.dial === countryCode) || null,
    [countries, countryCode]
  );

  useEffect(() => {
    if (!userId) {
      navigate("/");
    }
  }, [navigate, userId]);

  async function sendCode() {
    setError("");
    const dest =
      channel === "email"
        ? email.trim()
        : `${countryCode}${nationalNumber.replace(/\D/g, "")}`;

    setPhase("sending");
    try {
      const url =
        channel === "email"
          ? `${API_BASE}/auth/request-email-otp`
          : `${API_BASE}/auth/request-sms-otp`;
      const body =
        channel === "email"
          ? { userId, email: dest }
          : { userId, phoneNumber: dest };

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok && data.status === "sent") {
        localStorage.setItem("lastChannel", channel);
        localStorage.setItem("otpDest", dest);
        localStorage.setItem("smsDemo", "0");
        if (channel === "email") {
          localStorage.setItem("email", dest);
        } else {
          localStorage.setItem("countryCode", countryCode);
          localStorage.setItem("nationalNumber", nationalNumber);
        }
        navigate("/otp-enter");
      } else {
        setError(data.detail || "Échec de l'envoi.");
        setPhase("collect");
      }
    } catch {
      setError("Impossible de contacter le serveur Flask.");
      setPhase("collect");
    }
  }

  function onNationalChange(value) {
    const digits = value.replace(/\D/g, "");
    const max = selected?.maxLen || 15;
    setNationalNumber(digits.slice(0, max));
  }

  if (phase === "sending") {
    return (
      <Shell step={3}>
        <div className="step-label">Étape 3 / 4</div>
        <div className="icon-badge pulse">
          <LoaderCircle size={28} className="spin" />
        </div>
        <h2>{copy.sendingTitle}</h2>
        <div className="status-msg">Envoi en cours...</div>
      </Shell>
    );
  }

  return (
    <Shell step={3}>
      <div className="step-label">Étape 3 / 4</div>
      <div className="icon-badge">
        {channel === "email" ? <Mail size={28} /> : <MessageSquare size={28} />}
      </div>
      <h2>{copy.collectTitle}</h2>
      <p className="hint">{copy.collectHint}</p>

      {channel === "email" ? (
        <div className="field">
          <Mail size={18} />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="votre.email@exemple.com"
            autoComplete="email"
          />
        </div>
      ) : (
        <div className="phone-row">
          <select
            value={countryCode}
            onChange={(e) => setCountryCode(e.target.value)}
          >
            {countries.map((c) => (
              <option key={c.iso + c.dial} value={c.dial}>
                {c.dial} {c.name}
              </option>
            ))}
          </select>
          <input
            value={nationalNumber}
            onChange={(e) => onNationalChange(e.target.value)}
            placeholder={selected ? `${selected.minLen} chiffres` : "Numéro"}
            inputMode="numeric"
          />
        </div>
      )}
      {channel !== "email" && selected ? (
        <p className="hint">
          {selected.name} — {selected.minLen}
          {selected.minLen !== selected.maxLen ? ` à ${selected.maxLen}` : ""}{" "}
          chiffres, sans le 0 initial.
        </p>
      ) : null}

      <button
        onClick={sendCode}
        disabled={channel === "email" ? !email.trim() : !nationalNumber}
      >
        {copy.submit}
        <Send size={16} />
      </button>
      {error ? (
        <div className="error-msg">
          <CircleAlert size={16} />
          {error}
        </div>
      ) : null}
      <span className="link" onClick={() => navigate("/choose-channel")}>
        <ArrowLeft size={14} />
        Changer de canal
      </span>
    </Shell>
  );
}
