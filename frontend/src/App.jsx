import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import SelectPage from "./pages/SelectPage";
import TrainPage from "./pages/TrainPage";
import HistoryPage from "./pages/HistoryPage";
import NotFoundPage from "./pages/NotFoundPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import { useHistory } from "./hooks/useHistory";
import { useAuth, isTokenExpired } from "./hooks/useAuth";
import DashboardPage from "./pages/DashoardPage";
import VerifyOtpPage from "./pages/VerifyOtpPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ProfilePage from "./pages/ProfilePage";

export default function App() {
  const { history, fetchHistory, saveWorkout, isLoading } = useHistory();
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    const token = localStorage.getItem("token");
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
      localStorage.removeItem("token_saved_at");
      return false;
    }
    return true;
  });
  const handleFinish = (result, exercise) => {
    if (!result) return;
    // useHistory จัดการเองว่า login อยู่ไหม ถ้าไม่ login ก็ไม่เซฟ
    saveWorkout({ ...result, exercise });
  };

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-black text-white font-mono overflow-x-hidden">
        <Routes>
          <Route path="/"                element={<SelectPage />} />
         <Route
            path="/train/:exercise"
            element={
              <TrainPage
                onFinish={handleFinish}
                isLoggedIn={isLoggedIn} // ✅ ส่งลงไป
              />
            }
          />
          <Route path="/history"         element={<HistoryPage fetchHistory={fetchHistory} history={history} isLoading={isLoading} />} />
         <Route path="/login" element={<LoginPage onLogin={() => {
              setIsLoggedIn(true);
              const pending = sessionStorage.getItem('pendingWorkout');
              if (pending) {
                sessionStorage.removeItem('pendingWorkout');
                saveWorkout(JSON.parse(pending));
              }
            }} />} />
          <Route path="/register"        element={<RegisterPage />} />
          <Route path="*"               element={<NotFoundPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/verify-otp" element={<VerifyOtpPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/profile" element={<ProfilePage/>}/>
        </Routes>
      </div>
    </BrowserRouter>
  );
}