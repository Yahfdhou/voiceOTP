import { ShieldCheck } from "lucide-react";

export default function Shell({ step, children }) {
  return (
    <>
      <div className="app-bg">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
      </div>
      <div className="app-wrap">
        <div className="card">
          <div className="brand">
            <div className="brand-mark">
              <ShieldCheck size={22} />
            </div>
            <div>
              <div className="brand-name">Voice OTP</div>
              <div className="brand-sub">Vérification sécurisée</div>
            </div>
          </div>
          <div className="steps" aria-hidden="true">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className={`step-dot${n < step ? " done" : ""}${n === step ? " current" : ""}`}
              >
                <span />
              </div>
            ))}
          </div>
          {children}
        </div>
      </div>
    </>
  );
}
