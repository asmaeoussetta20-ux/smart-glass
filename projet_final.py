import RPi.GPIO as GPIO
import time
import subprocess
from picamera2 import Picamera2
from ultralytics import YOLO
from RPLCD.gpio import CharLCD

# === GPIO ===
TRIG   = 23
ECHO   = 24
BUZZER = 18
SEUIL  = 100

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG,   GPIO.OUT)
GPIO.setup(ECHO,   GPIO.IN)
GPIO.setup(BUZZER, GPIO.OUT)
GPIO.output(BUZZER, GPIO.LOW)

# === LCD ===
lcd = CharLCD(
    pin_rs=25, pin_e=19,
    pins_data=[13, 6, 5, 11],
    numbering_mode=GPIO.BCM,
    cols=16, rows=2
)

def lcd_afficher(ligne1, ligne2=""):
    lcd.clear()
    lcd.write_string(ligne1[:16])
    lcd.cursor_pos = (1, 0)
    lcd.write_string(ligne2[:16])

def lcd_defiler(texte, ligne=0, vitesse=0.3):
    texte = "  " + texte + "  "
    for i in range(len(texte) - 15):
        lcd.cursor_pos = (ligne, 0)
        lcd.write_string(texte[i:i+16])
        time.sleep(vitesse)

# === Ecran démarrage ===
lcd_afficher("** SMART GLASS **", "FOR BLIND PERSON")
time.sleep(3)

membres = [
    ("ASMAE",   "OUSSETTA"),
    ("NASSIMA", "MOUFIDI"),
    ("Radoua",  "Taoufiq"),
    ("MOUAD",   "OKHAM"),
]
for prenom, nom in membres:
    lcd_afficher(f"  {prenom}", f"  {nom}")
    time.sleep(2)

lcd_afficher("Systeme actif", "En attente...")

# === Caméra + YOLO ===
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()
time.sleep(2)

model = YOLO("yolo11n.pt")

# === Fonctions ===
def mesure_distance():
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)
    debut = time.time()
    while GPIO.input(ECHO) == 0:
        debut = time.time()
    fin = time.time()
    while GPIO.input(ECHO) == 1:
        fin = time.time()
    dist = round((fin - debut) * 34300 / 2, 1)
    if dist > 400:
        return 999
    return dist

def parler(texte):
    print(f"🔊 {texte}")
    subprocess.run(["espeak", "-v", "fr", "-s", "130", texte],
                   stderr=subprocess.DEVNULL)

def alarme(duree=2):
    GPIO.output(BUZZER, GPIO.HIGH)
    time.sleep(duree)
    GPIO.output(BUZZER, GPIO.LOW)

print("=== Système actif : Ultrason + YOLO + Voix ===")
print("Ctrl+C pour arrêter\n")

try:
    while True:
        dist = mesure_distance()
        if dist == 999:
            time.sleep(0.3)
            continue

        print(f"📏 Distance : {dist} cm")

        if dist < SEUIL:
            print(f"⚡ Objet proche ({dist} cm) → Analyse YOLO...")
            lcd_afficher("Analyse...", f"Dist: {int(dist)} cm")

            frame = picam2.capture_array()
            results = model(frame, imgsz=320, verbose=False)
            names  = results[0].names
            boxes  = results[0].boxes
            detections = [names[int(b.cls)] for b in boxes]
            print(f"   Détections : {detections}")

            for obj in set(detections):
                message = f"{obj} detecte a {int(dist)} centimetres"
                parler(message)
                lcd_afficher(f"  {obj[:16]}", f"  {int(dist)} cm")
                time.sleep(1)

            if detections:
                print(f"   🚨 Objet détecté → ALARME !")
                alarme(duree=2)
            else:
                print("   ✅ Rien détecté")
                lcd_afficher("Rien detecte", "En attente...")

            time.sleep(3)
            lcd_afficher("Systeme actif", "En attente...")
        else:
            time.sleep(0.3)

except KeyboardInterrupt:
    print("\nArrêt du système.")
    lcd_afficher("  Au revoir !", " Smart Glass  ")
    time.sleep(2)
    lcd.clear()
    GPIO.output(BUZZER, GPIO.LOW)
    GPIO.cleanup()
    picam2.stop()
