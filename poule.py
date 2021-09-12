#!/usr/bin/python3
# -*- coding:utf-8 -*-
import sys
import os
import logging
import logging.handlers
# import socket
import time
import traceback
from datetime import datetime, timedelta
import json
import ephem
import pytz
from picamera import PiCamera
import RPi.GPIO as GPIO
from signal import signal, SIGINT, SIGTERM, SIGHUP

# import random
from paho.mqtt import client as mqtt_client

from subprocess import check_output


#######################################################
## MQTT
broker = '192.168.30.1'
port = 1883
base_topic = "poulailler/"
client_id = 'poulailler'
username = ''
password = ''

#######################################################
# Coordonnées
LOC_LAT = '49.013443'
LOC_LONG = '1.967827'
LOC_TZ = 'Europe/Paris'

#######################################################
# Delais montee et descente (en secondes)
DELAI_DESC = 7
DELAI_MONT = 7

# Delta ouverture / Fermeture (en minutes)
OFFSET_MATIN = 15 # xx minutes après le lever du soleil
OFFSET_SOIR = 15  # xx minutes apres le coucher du soleil

#######################################################
# GPIOs

# PIN GPIO Relais
GPIO_RL_1 = 6 # Alim moteur
GPIO_RL_2 = 13 # Sens de rotation +
GPIO_RL_3 = 19 # Sens de rotation - 
GPIO_RL_4 = 26 # N/A
GPIO_RL_5 = 5  # N/A
GPIO_RL_6 = 7 # N/A

# PIN GPIO Fins de course
GPIO_FC_H = 21
GPIO_FC_B = 20 

# Boutons poussoirs montee/descente/stop
GPIO_BP_UP = 12
GPIO_BP_DOWN = 16
GPIO_BP_STOP = 9

# Capteur de mouvement
GPIO_MVT = 14

# Capteur luminosite
GPIO_LUMINOSITE = 2

#######################################################
## Chemin des images
# PICDIR = 'pic' # Points to pic directory .

# Logger
logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s')
my_logger = logging.getLogger('MyLogger')
my_logger.setLevel(logging.DEBUG)

# handler = logging.handlers.SysLogHandler(address = '/dev/log')
# my_logger.addHandler(handler)

class Poulailler:
    "Gestion du poulailler"

    # -------------------------------------------
    
    # Client MQTT
    client = None
    client_connected = False

    # camera
    camera = None

    # Etat de la porte
    STATE_OPEN = 1      # ouverte
    STATE_CLOSED = 0    # fermee
    STATE_MID  = -1     # Au milieu - aucun capteur
    STATE_ERR  = -2     # Bizare, les 2 capteurs en mm tps

    # Jours nuit
    DAYLIGHT = None
    
    # Jours nuit
    CAMERA_CONNECTED = False

    #######################################################
    # Constructeur
    def __init__(self):
        
        # -------------------------------------------
        # init GPIO
        my_logger.info("Initialise GPIO")
        try: 
            # on passe en mode BMC qui veut dire que nous allons utiliser directement
            # le numero GPIO plutot que la position physique sur la carte
            GPIO.setmode(GPIO.BCM)
            # GPIO.setwarnings(False)
            
            # entrées fin de course
            GPIO.setup(GPIO_FC_H, GPIO.IN, GPIO.PUD_UP)
            GPIO.setup(GPIO_FC_B, GPIO.IN, GPIO.PUD_UP)

            # on défini les BP up et down
            GPIO.setup(GPIO_BP_UP, GPIO.IN, GPIO.PUD_DOWN)
            GPIO.setup(GPIO_BP_DOWN, GPIO.IN, GPIO.PUD_DOWN)
            GPIO.setup(GPIO_BP_STOP, GPIO.IN, GPIO.PUD_DOWN)


            # Action sur BP up/down:
            # GPIO.add_event_detect(GPIO_BP_UP, GPIO.FALLING, callback=self.porte_ouvre, bouncetime=1000)
            # GPIO.add_event_detect(GPIO_BP_DOWN, GPIO.FALLING, callback=self.porte_ferme, bouncetime=1000)
            
            # Action sur BP Stop
            # todo Ajouter une resistance de pull-* 
            # GPIO.add_event_detect(GPIO_BP_STOP, GPIO.FALLING, callback=self.porte_stop, bouncetime=500)


            # sortie output relais, ouvert par défaut
            GPIO.setup(GPIO_RL_1, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(GPIO_RL_2, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(GPIO_RL_3, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(GPIO_RL_4, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(GPIO_RL_5, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(GPIO_RL_6, GPIO.OUT, initial = GPIO.HIGH)

            # Detecteur de luminostite
            GPIO.setup(GPIO_LUMINOSITE, GPIO.IN)

            # Detecteur de mouvement
            # GPIO.setup(GPIO_MVT, GPIO.IN)
            # GPIO.add_event_detect(GPIO_MVT , GPIO.BOTH, callback=self.detection_mvt)

            time.sleep(2)
            my_logger.debug("- Init GPIO OK")

        except IOError as e:
            my_logger.info(e)
            sys.exit("ERREUR init GPIO")
        
	    # init MQTT
        self.client = self.connect_mqtt()
        self.publish("ip", check_output(['hostname', '-I']))
        self.subscribe("set")
        self.client.loop_start()

        # -------------------------------------------
        # Init de la camera
        try: 
            self.camera = PiCamera()
            self.camera.resolution = (1280, 720)
            self.camera.start_preview()
            self.CAMERA_CONNECTED = True
        except: 
            my_logger.info("Erreur picam")
        
        # Camera warm-up time
        time.sleep(2)
        

    # -------------------------------------------
    # Destructeur
    def __del__(self):
        '''
        try: 
            GPIO.cleanup()
        except RuntimeWarning:
            pass
        '''

    #######################################################
    # MQTT
    def connect_mqtt(self):


        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                # my_logger.info("Connectée au broker MQTT")
                # self.publish("mqtt", "connected")
                self.client_connected = True
                my_logger.info("Connecté à MQTT rc = {}".format(rc))
                pass
            else:
                self.client_connected = False
                my_logger.error("Connexion MQTT impossible - Code d'erreur {}".format(rc))

        client = mqtt_client.Client(client_id)
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        try:
            client.connect(broker, port)
        except OSError as e:
            my_logger.error('Connexion MQTT impossible {}'.format(e))
    

        return client

    def subscribe(self, topic):
        def on_message(client, userdata, msg):
            my_logger.debug(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
            if msg.payload.decode() == 'up':
                self.porte_ouvre()
            elif msg.payload.decode() == 'down':
                self.porte_ferme()
            else:
                pass


        self.client.subscribe(base_topic + topic)
        self.client.on_message = on_message


    def publish(self, topic, msg = ""):

        if self.client_connected == False:
            return

        result = self.client.publish(base_topic + topic, msg, qos=0,retain=True)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            my_logger.debug(f"Send `{msg}` to topic `{topic}`")
        else:
            my_logger.error(f"Failed to send message to topic {topic}")


    def publie_event(self, pin):
        self.publish("in_gpio_{}".format(pin), GPIO.input(pin))
        
    #######################################################
    # Actionneurs
    
    # -------------------------------------------
    # Set Relais
    # @param int numéro du relai
    # @param bool etat True = fermé, False = ouvert
    def setRL(self, RL, etat = False):
        if etat == False:
            GPIO.output(globals()[f"GPIO_RL_{RL}"], GPIO.HIGH)
            my_logger.debug(f"Set relais {RL} OFF")
            self.publish("relais_{}".format(RL), "OFF" )
        elif etat == True:
            GPIO.output(globals()[f"GPIO_RL_{RL}"], GPIO.LOW)
            my_logger.debug(f"Set relais {RL} ON")
            self.publish("relais_{}".format(RL), "ON")
        else:
            my_logger.error(f"Etat {etat} inconnu")



    # -------------------------------------------
    def porte_ouvre(self, pin = None):

        my_logger.debug("OUVRE Evenement sur pin {}".format(pin))
        
        # Position en erreur
        state = self.porte_etat()
        if state == self.STATE_ERR:
            my_logger.error("Erreur position porte: les 2 contacteurs de position sont actionnés")
            return False

        # porte déja ouverte ? On ne fait rien
        if state == self.STATE_OPEN:
            my_logger.info("Porte deja ouverte")
            return True

        # etat du moteur
        if pin is not None and GPIO.input(GPIO_RL_1) == GPIO.LOW:
            my_logger.info("Moteur deja en marche - Patience")
            return True

        my_logger.info("▲ Debut montée")
        
        self.setRL(2, True)
        self.setRL(3, True)
        self.setRL(1, True)

        # On attend la fin de la descente, ou le timeout

        # 8 secondes
        self.setRL(4, True)
        t_end = time.time() + DELAI_MONT
        while time.time() < t_end and GPIO.input(GPIO_FC_H) == 0:
            time.sleep(.05)
        self.setRL(4, False)

        my_logger.debug("porte etat {}".format(self.porte_etat()))

        self.setRL(1, False)
        self.setRL(2, False)
        self.setRL(3, False)
        return True

   
    # -------------------------------------------
    def porte_ferme(self, pin=None):

        my_logger.debug("FERME Evenement sur pin {}".format(pin))

        # Position en erreur
        state = self.porte_etat()
        if state == self.STATE_ERR:
            my_logger.error("Erreur position porte: les 2 contacteurs de position sont actionnés")
            return False

        # porte déja fermee ? On ne fait rien
        if state == self.STATE_CLOSED:
            my_logger.info("Porte déja fermée")
            return True
        
        if pin is not None and GPIO.input(GPIO_RL_1) == GPIO.LOW:
            my_logger.info("Moteur deja en marche - Patience...")
            return True

        my_logger.info("▼ Debut descente")

        self.setRL(2, False)
        self.setRL(3, False)
        self.setRL(1, True)
        
        # 8 secondes
        self.setRL(4, True)
        t_end = time.time() + DELAI_DESC
        while time.time() < t_end and GPIO.input(GPIO_FC_B) == 0:
            time.sleep(.05)
        self.setRL(4, False)
                  

        my_logger.debug("porte etat {}".format(self.porte_etat()))
        self.setRL(1, False)
        return True



    def porte_stop(self, pin = None):
        my_logger.debug("STOP Evenement sur pin {}".format(pin))
        my_logger.debug("porte etat {}".format(self.porte_etat()))
        # my_logger.info("✖ Btn STOP > Arret moteur")
        self.setRL(1, False)
        self.setRL(4, False)


    
    #######################################################
    # Getteur


    # -------------------------------------------
    # Position de la porte
    # 1: ouverte
    # 0: fermée
    # -1: entre-deux
    # -2: Etat schrödinger (ouverte & fermee en mm tps)
    def porte_etat(self):
        
        fc_h = GPIO.input(GPIO_FC_H) # fin course haut
        fc_b = GPIO.input(GPIO_FC_B) # fin course bas

        my_logger.debug(f"FC_H: {fc_h} - FC-B: {fc_b}")
        # erreur
        if fc_h == 1 and fc_b == 1:
            self.publish('porte_etat', self.STATE_ERR)
            return self.STATE_ERR
        # Milieu
        elif fc_h == 0 and fc_b == 0:
            self.publish('porte_etat', self.STATE_MID)
            return self.STATE_MID
        # Ouverte
        elif fc_h == 1 and fc_b == 0:
            self.publish('porte_etat', self.STATE_OPEN)
            return self.STATE_OPEN
        # Fermee 
        elif fc_h == 0 and fc_b== 1:
            self.publish('porte_etat', self.STATE_CLOSED)
            return self.STATE_CLOSED

        # erreur par défaut
        self.publish('porte_etat', self.STATE_ERR)
        return self.STATE_ERR


    #######################################################
    # Gestion du temps

    # -------------------------------------------
    # Est-ce qu'il fait jour ? 
    # @return bool True=jour, Flase=nuit
    
    def is_jour(self):        
        home        = ephem.Observer()  
        home.lon    = LOC_LONG            # str() Longitude
        home.lat    = LOC_LAT           # str() Latitude

        next_sunrise    = home.next_rising(ephem.Sun()).datetime() .replace(tzinfo=pytz.utc).astimezone(pytz.timezone(LOC_TZ)) + timedelta(minutes=OFFSET_MATIN)
        next_sunset     = home.next_setting(ephem.Sun()).datetime().replace(tzinfo=pytz.utc).astimezone(pytz.timezone(LOC_TZ)) + timedelta(minutes=OFFSET_SOIR)
        
        return (bool)(next_sunset < next_sunrise) 
    

    # -------------------------------------------
    # Luminosite
    # @return True=jour, false sinon
    def daylight(self):
        # Nuit
        if GPIO.input(GPIO_LUMINOSITE):
            self.publish('capteur lumiere', 'nuit')
            my_logger.info("Capteur luminosite: Nuit {}".format('\u263e'))
            return False 
        # Jour
        else:
            self.publish('capteur lumiere', 'jour')
            my_logger.info("Capteur luminosite: Jour {}".format('\u263c'))
            return True 
   

    #  On prend une photo
    def photo(self):
        if self.CAMERA_CONNECTED == True:
            my_logger.info('Prise de photo')
            now = datetime.now()
            self.camera.annotate_text = now.strftime("%d/%m/%Y %H:%M:%S")
            self.camera.capture('/var/www/html/poulailler.jpg')
        else:
            my_logger.info('PICAM non disponnible')


    # -------------------------------------------
    # Programme principal
    def run(self):

        state = self.porte_etat()
        
        daylight = self.daylight()
        
        # Je publie les delta matin et soir, pour controles extérieurs
        # self.publish('OFFSET_MATIN', OFFSET_MATIN)
        # self.publish('OFFSET_SOIR', OFFSET_SOIR)
        my_logger.debug("Etat porte {}".format(state))

        # Position en erreur
        if state == self.STATE_ERR:
            sys.exit("Erreur position porte: les 2 contacteurs de position sont actionnés")
        
        # On défini l'état de la porte au lancement
        # jour et porte fermée ou au milieu: On l'ouvre
        if True ==  daylight and state != self.STATE_OPEN:
            my_logger.info("Jour et porte non ouverte -> Je l'ouvre")
            etat = self.porte_ouvre()
        
        # Nuit et porte ouverte
        elif False == daylight and state != self.STATE_CLOSED:
            my_logger.info("Nuit et porte non ouverte -> Je la ferme")
            etat = self.porte_ferme()
        
        # OK, jour et porte ouverte
        elif True == daylight and state == self.STATE_OPEN:
            my_logger.info('Jour et porte ouverte -> OK')
        
        # OK, nuit et porte fermee
        elif False == daylight and state == self.STATE_CLOSED:
            my_logger.info('Nuit et porte fermee -> OK')
        else:
            my_logger.debug("Etat bizare ?!?")
       


        # -------------------------------------------
        #Boucle infinie
        my_logger.debug("Demarrage programme principal")
        old_daylight = daylight
        while True:                   
            daylight = self.daylight()
           
            self.photo()

            # Si il est l'heure est dépassée, et que la luminosite a changée:
            if daylight != old_daylight:

                if daylight == True:
                    my_logger.info('\u263c Cocorico , il fait jour !')
                    self.porte_ouvre()
                else:
                    my_logger.info('\u263e ZZzzz, c\'est l\'heure de dormir !')
                    self.porte_ferme()

            
            # On vérifie la connexion MQTT
            if self.client_connected == False:
                self.client = self.connect_mqtt()

            # On publie la date & heure
            # self.publish('datetime', datetime.now().strftime("%d/%m/%Y %H:%M"))
            self.publish('datetime', int(time.time()))

            # On vérifie toutes les minutes l'état de la lumiere
            time.sleep(60)   # Attente XX secondes
            old_daylight = daylight



    '''
    def detection_mvt(self, channel):
        if GPIO.input(channel):     # if port 25 == 1  
            my_logger.debug("Mouvement detecté sur port {}".format(channel))  
        else:                  # if port 25 != 1  
            my_logger.debug("Absence mouvement sur port {}".format(channel))  
        # my_logger.debug('Mouvement detecté! {}'.format(channel))
    '''





# -------------------------------------------
# On gère un cleanup propre
def handler(signal_received, frame):
    exit("Interruption du programme")
    GPIO.cleanup()


if __name__ == '__main__':
    
    # On prévient Python d'utiliser la method handler quand un signal SIGINT est reçu
    signal(SIGTERM, handler)
    signal(SIGINT, handler)
    signal(SIGHUP, handler)

    p = Poulailler()
    try:    
        p.run()
    except SystemExit as e:
        my_logger.error("Sortie anormale: {}".format(e))
        GPIO.cleanup()
        


