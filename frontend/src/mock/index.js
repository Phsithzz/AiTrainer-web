import axios from 'axios';

if (import.meta.env.VITE_IS_MOCK === "true") {
  console.log("🚀 Portfolio Mock Mode Enabled");

  const delay = (ms = 300) => new Promise(r => setTimeout(r, ms));
  const time = (hoursAgo) => new Date(Date.now() - hoursAgo * 3600000).toISOString();

  // 1. Mock Axios HTTP Requests
  axios.get = async (url, config) => {
    await delay();
    if (url.includes('/auth/me')) return { data: { username: 'Portfolio Guest', email: 'guest@portfolio.com' } };
    if (url.includes('/exercise/workouts')) return { 
      data: [ 
        { id: 1, exercise: 'squat', total_reps: 15, duration_sec: 60, created_at: time(1), stats: { squat_good: 10, squat_bad_heel: 3, squat_bad_back: 2 } },
        { id: 2, exercise: 'pushup', total_reps: 20, duration_sec: 90, created_at: time(24), stats: { pushup_good: 18, pushup_bad_hips: 2 } },
        { id: 3, exercise: 'plank', duration_sec: 120, created_at: time(48), stats: { plank_good: 110, plank_bad_hips: 10 } }
      ] 
    };
    return { data: {} };
  };
  
  axios.post = async (url, data, config) => {
    await delay();
    if (url.includes('/auth/login')) return { data: { access_token: 'mock-token-123', username: 'Portfolio Guest' } };
    if (url.includes('/auth/register')) return { data: { message: 'Registered' } };
    if (url.includes('/exercise/workouts')) return { data: { message: 'Saved' } };
    return { data: { message: "Mock success" } };
  };

  axios.put = async (url, data, config) => {
    await delay();
    return { data: { message: 'Mock updated' } };
  };

  // 2. Mock Fetch for Dashboard
  const originalFetch = window.fetch;
  window.fetch = async (url, options) => {
    await delay();
    if (typeof url === 'string' && url.includes('/exercise/dashboard')) {
      return {
        ok: true,
        json: async () => ({
          my_stats: {
            total_reps: 35,
            total_time: 120,
            average_accuracy: 92,
            reps_by_ex: { squat: 15, pushup: 20 },
            time_by_ex: { plank: 120 },
            acc_by_ex: { squat: 90, pushup: 94 },
            weaknesses: [['squat_bad_heel', 3], ['squat_bad_back', 2], ['pushup_bad_hips', 2]]
          },
          global_stats: {
            reps_by_ex: { squat: 20, pushup: 15 },
            time_by_ex: { plank: 90 }
          },
          comparison: {
            is_above_average_time: true,
            is_above_average_acc: true
          }
        })
      };
    }
    return originalFetch(url, options);
  };

  // 3. Mock WebSocket for Real-time AI Tracking
  class MockWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 1; // OPEN
      this.exercise = url.split('/').pop();
      this.good_count = 0;
      this.bad_count = 0;
      this.bad_details = {};
      this.total_time = 0;
      this.lastY = null;
      this.isDown = false;
      this.frames = 0;
      this.lastTime = Date.now();
      
      setTimeout(() => {
        if (this.onopen) this.onopen();
      }, 100);
    }
    
    send(data) {
      const parsed = JSON.parse(data);
      if (parsed.action === 'reset') {
        this.good_count = 0;
        this.bad_count = 0;
        this.bad_details = {};
        this.total_time = 0;
        this.frames = 0;
        this.isDown = false;
        this.lastY = null;
        if (this.onmessage) this.onmessage({ data: JSON.stringify({ action: 'reset_ok' }) });
        return;
      }
      
      if (parsed.action === 'predict' && parsed.landmarks) {
        this.frames++;
        const now = Date.now();
        const dt = (now - this.lastTime) / 1000;
        this.lastTime = now;

        const nose = parsed.landmarks[0];
        const noseY = nose ? nose.y : 0.5;
        
        let label = this.exercise + "_good";
        let feedback = "";
        let newRep = false;

        if (this.exercise === "squat" || this.exercise === "pushup") {
          if (this.lastY !== null) {
            if (noseY > this.lastY + 0.015) {
              this.isDown = true;
            } else if (noseY < this.lastY - 0.015 && this.isDown) {
              this.isDown = false;
              newRep = true;
            }
          }
          this.lastY = noseY;

          if (newRep) {
            const isBad = Math.random() < 0.25;
            if (isBad) {
              if (this.exercise === "squat") {
                label = Math.random() > 0.5 ? "squat_bad_heel" : "squat_bad_back";
                feedback = label === "squat_bad_heel" ? "ส้นเท้าลอย! ถ่ายน้ำหนักลงส้นเท้า" : "หลังโค้ง! ยืดอกขึ้น เกร็งหน้าท้อง";
              } else {
                const badTypes = ["pushup_bad_hips", "pushup_bad_legs", "pushup_bad_neck"];
                label = badTypes[Math.floor(Math.random() * badTypes.length)];
                feedback = label === "pushup_bad_hips" ? "สะโพกยกหรือห้อย! ล็อคแกนกลางลำตัวให้ตรง" : "ขางอ! เหยียดขาให้ตึงตลอดเวลา";
              }
              this.bad_count++;
              this.bad_details[label] = (this.bad_details[label] || 0) + 1;
            } else {
              this.good_count++;
              label = this.exercise + "_good";
            }
          }
        } else if (this.exercise === "plank") {
          if (dt > 0 && dt < 1) {
            this.total_time += dt;
          }
          if (Math.random() < 0.05) {
            const badTypes = ["plank_bad_hips", "plank_bad_legs", "plank_bad_neck"];
            label = badTypes[Math.floor(Math.random() * badTypes.length)];
            feedback = "สะโพกโด่งหรือตก! เกร็งหน้าท้องให้ลำตัวขนานกับพื้น";
            this.bad_details[label] = (this.bad_details[label] || 0) + 1;
            this.bad_count++;
          } else {
            label = "plank_good";
          }
        }

        setTimeout(() => {
          if (this.onmessage) {
            this.onmessage({
              data: JSON.stringify({
                pose_detected: true,
                label: label,
                confidence: 0.95,
                feedback: feedback,
                reps: this.good_count + this.bad_count,
                good_count: this.good_count,
                bad_count: this.bad_count,
                bad_details: this.bad_details,
                state: this.isDown ? "DOWN" : "UP",
                total_time: Math.round(this.total_time * 10) / 10,
                is_holding: this.exercise === "plank",
                elbow_angle: this.exercise === "pushup" ? (this.isDown ? 85 : 160) : null,
                landmarks: parsed.landmarks,
                proba: { [label]: 0.95 }
              })
            });
          }
        }, 30);
      }
    }
    
    close() {
      this.readyState = 3;
      if (this.onclose) this.onclose();
    }
  }

  // Override native WebSocket with our mock
  window.WebSocket = MockWebSocket;
}
