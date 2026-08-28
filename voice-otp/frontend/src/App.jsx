import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import ChooseChannel from "./pages/ChooseChannel.jsx";
import OtpCall from "./pages/OtpCall.jsx";
import OtpVerify from "./pages/OtpVerify.jsx";
import OtpEnter from "./pages/OtpEnter.jsx";
import Success from "./pages/Success.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/choose-channel" element={<ChooseChannel />} />
      <Route path="/otp-call" element={<OtpCall />} />
      <Route path="/otp-sms" element={<OtpVerify channel="sms" />} />
      <Route path="/otp-email" element={<OtpVerify channel="email" />} />
      <Route path="/otp-enter" element={<OtpEnter />} />
      <Route path="/success" element={<Success />} />
    </Routes>
  );
}
