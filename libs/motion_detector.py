import math
import time

class SmartMotionDetector:
    def __init__(self, 
                 alpha=0.8,              # Coefficiente passa-alto (0.7 - 0.9)
                 energy_threshold=0.18,  # Soglia minima di movimento continuo
                 sustain_ms=350,         # Durata minima del movimento (ignora urti < 350ms)
                 tilt_threshold_rad=0.25): # ~14 gradi di variazione di inclinazione
        
        self.alpha = alpha
        self.energy_threshold = energy_threshold
        self.sustain_ms = sustain_ms
        self.tilt_threshold = tilt_threshold_rad
        
        # Componente a bassa frequenza (gravità statica stimata)
        self.gravity = [0.0, 0.0, 1.0]
        
        # Riferimento di orientamento a riposo (vettore gravità normalizzato)
        self.ref_gravity = [0.0, 0.0, 1.0]
        
        # Tracciamento temporale del movimento continuo
        self.motion_start_ms = None

    def reset_reference(self, initial_accel):
        """Chiama questo metodo quando la sessione inizia e il telefono è fermo."""
        if initial_accel is None:
            raise ValueError("Missing calibration sample")
        ax, ay, az = initial_accel
        norm = math.sqrt(ax * ax + ay * ay + az * az)
        if not math.isfinite(norm) or norm < 0.1:
            raise ValueError("Invalid gravity reference")
        self.gravity = [ax, ay, az]
        self.ref_gravity = [ax / norm, ay / norm, az / norm]
        self.motion_start_ms = None

    def update(self, raw_accel):
        """
        Ritorna True quando inclinazione o accelerazione superano le soglie.
        Con sustain_ms=0 basta un campione di accelerazione sopra soglia.
        Eseguire a frequenza costante (es. ogni 20-50ms).
        """
        if raw_accel is None:
            self.motion_start_ms = None
            return False
        now = time.ticks_ms()
        ax, ay, az = raw_accel

        # 1. Stima della gravità tramite filtro passa-basso (Low-Pass)
        self.gravity[0] = self.alpha * self.gravity[0] + (1.0 - self.alpha) * ax
        self.gravity[1] = self.alpha * self.gravity[1] + (1.0 - self.alpha) * ay
        self.gravity[2] = self.alpha * self.gravity[2] + (1.0 - self.alpha) * az

        # 2. Accelerazione dinamica tramite passa-alto (High-Pass: Segnale - Gravità)
        linear_x = ax - self.gravity[0]
        linear_y = ay - self.gravity[1]
        linear_z = az - self.gravity[2]
        
        dynamic_energy = math.sqrt(linear_x**2 + linear_y**2 + linear_z**2)

        # 3. Controllo dell'inclinazione (Tilt) rispetto alla posizione di partenza
        # Prodotto scalare tra vettore gravità iniziale e corrente
        g_norm = math.sqrt(self.gravity[0]**2 + self.gravity[1]**2 + self.gravity[2]**2) or 1.0
        dot_product = (self.gravity[0] * self.ref_gravity[0] +
                       self.gravity[1] * self.ref_gravity[1] +
                       self.gravity[2] * self.ref_gravity[2]) / g_norm
        
        # Clamp per evitare errori di precisione float in acos
        dot_product = max(-1.0, min(1.0, dot_product))
        angular_tilt = math.acos(dot_product)

        # 4. Condizione A: Cambio di inclinazione netto (il telefono è stato preso in mano)
        if angular_tilt > self.tilt_threshold:
            return True

        # 5. Condizione B: Accelerazione dinamica sopra soglia
        if dynamic_energy > self.energy_threshold:
            if self.motion_start_ms is None:
                self.motion_start_ms = now
            if time.ticks_diff(now, self.motion_start_ms) >= self.sustain_ms:
                # Rispetta la durata configurata, incluso lo scatto immediato.
                return True
        else:
            # Ritorno sotto soglia: resetta il timer.
            self.motion_start_ms = None

        return False
