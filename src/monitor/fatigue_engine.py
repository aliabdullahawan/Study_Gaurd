import time
from model.fatigue_state import FatigueState

class FatigueDecisionEngine:
    def __init__(self, cooldown_seconds=60):
        self.current_state = FatigueState.NORMAL
        
        # Scoring System
        self.fatigue_score = 0
        self.SCORE_THRESHOLD_WARNING = 50
        self.SCORE_THRESHOLD_ALERT = 100
        
        # Cooldown management
        self.last_alert_time = 0
        self.COOLDOWN_SECONDS = cooldown_seconds

    def evaluate_state(self, vision_snapshot, mouse_active, keyboard_active):
        current_time = time.time()
        is_eyes_closed = vision_snapshot.get("is_prolonged_closure", False)
        is_yawning = vision_snapshot.get("is_yawning", False)
        is_bad_posture = vision_snapshot.get("is_bad_posture", False)
        
        # 1. IF ALARM / COOLDOWN IS ACTIVE (Triggered by eye closure or head tilt reaching 100)
        if self.current_state == FatigueState.COOLDOWN:
            # Only exit cooldown if BOTH eyes are open AND posture is straight!
            if not is_eyes_closed and not is_bad_posture:
                self.current_state = FatigueState.NORMAL
                self.fatigue_score = 0
                return self._generate_report(reason="Fatigue condition resolved. Resetting to normal.")
            else:
                self.fatigue_score = 100
                return self._generate_report(reason="Critical fatigue condition active.")

        # 2. IMMEDIATE CRITICAL TRIGGER: Prolonged Eye Closure (Instant 100)
        if is_eyes_closed:
            self.fatigue_score = 100
            self.current_state = FatigueState.COOLDOWN
            self.last_alert_time = current_time
            return self._generate_report(reason="Critical: Prolonged eye closure detected.")

        # 3. PROGRESSIVE SCORE INCREASE FOR YAWNS & HEAD TILT
        if is_yawning:
            self.fatigue_score = min(50, self.fatigue_score + 10)
        elif is_bad_posture:
            self.fatigue_score += 5   # Slowly rises per second while slouching/tilting
        else:
            # Healing / Idle behavior when no negative vision signs are present
            if not mouse_active and not keyboard_active:
                self.fatigue_score += 1   
            else:
                self.fatigue_score = max(0, self.fatigue_score - 10)

        # Hard cap score between 0 and 100
        self.fatigue_score = min(100, max(0, self.fatigue_score))

        # 4. State Machine Transitions
        reason = "Normal activity."
        
        if self.fatigue_score >= self.SCORE_THRESHOLD_ALERT:
            self.current_state = FatigueState.COOLDOWN
            self.last_alert_time = current_time
            self.fatigue_score = 100
            reason = "Cumulative fatigue limit reached (Head Tilt / Posture)."
            
        elif self.fatigue_score >= self.SCORE_THRESHOLD_WARNING:
            self.current_state = FatigueState.DROWSY
            reason = "Elevated fatigue signs detected (Yawn/Posture)."
            
        elif self.fatigue_score > 0:
            self.current_state = FatigueState.POSSIBLY_FATIGUED
            
        else:
            self.current_state = FatigueState.NORMAL

        return self._generate_report(reason)

    def _generate_report(self, reason):
        return {
            "state": self.current_state.value,
            "score": self.fatigue_score,
            "explanation": reason,
            "trigger_alarm": self.current_state == FatigueState.COOLDOWN
        }