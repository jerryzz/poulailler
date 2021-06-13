#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import logging
# import socket
import time
import traceback
import datetime

from astral import LocationInfo
from astral.sun import sun
from lib.waveshare_epd import epd1in54_V2
from PIL import Image,ImageDraw,ImageFont
import RPi.GPIO as GPIO
from signal import signal, SIGINT

import pytz
utc=pytz.UTC

# Logger
logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
# logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)


class Poulailler:
    "Gestion du poulailler"

    ###################
    # PARAMETRES
    ################### 

    # Coordonnées
    LOC_VILLE = "Paris"
    LOC_PAYS  = "France"
    LOC_TZ = "Europe/Paris"
    LOC_COORD = (49.013443, 1.967827)

    # PIN GPIO Relais
    GPIO_RL_1 = 6 # Alim moteur
    GPIO_RL_2 = 13 # Sens de rotation +
    GPIO_RL_3 = 19 # Sens de rotation - 
    GPIO_RL_4 = 26 # N/A
    GPIO_RL_5 = 5  # N/A
    GPIO_RL_6 = 15 # N/A


    # PIN GPIO Fin de course
    GPIO_FC_H = 21
    GPIO_FC_B = 20 

    # Boutons poussoirs montee/descente/stop
    GPIO_BP_UP = 12
    GPIO_BP_DOWN = 16
    GPIO_BP_STOP = 4

    # Capteur de mouvement
    GPIO_MVT = 14

    ## Chemin des images
    PICDIR = 'pic' # Points to pic directory .

   
    # Action en cours 
    # -1 Descente , 0 arret, 1 montee
    ACTION = 0

    # Etat de la porte
    STATE_OPEN = 1
    STATE_CLOSED = 0
    STATE_MID  = -1
    STATE_ERR  = -2 

    
    # Constructeur
    def __init__(self):
        
        # -------------------------------------------
        # init GPIO
        logging.info("Initialise GPIO")
        try: 
            # on passe en mode BMC qui veut dire que nous allons utiliser directement
            # le numero GPIO plutot que la position physique sur la carte
            GPIO.setmode(GPIO.BCM)
            # GPIO.setwarnings(False)
            
            # entrées fin de course
            GPIO.setup(self.GPIO_FC_H, GPIO.IN, GPIO.PUD_UP)
            GPIO.setup(self.GPIO_FC_B, GPIO.IN, GPIO.PUD_UP)

            # on défini les BP up et down
            GPIO.setup(self.GPIO_BP_UP, GPIO.IN, GPIO.PUD_DOWN)
            GPIO.setup(self.GPIO_BP_DOWN, GPIO.IN, GPIO.PUD_DOWN)
            GPIO.setup(self.GPIO_BP_STOP, GPIO.IN, GPIO.PUD_DOWN)

            GPIO.add_event_detect(self.GPIO_BP_UP, GPIO.FALLING, callback=self.porte_ouvre, bouncetime=1000)
            GPIO.add_event_detect(self.GPIO_BP_DOWN, GPIO.FALLING, callback=self.porte_ferme, bouncetime=1000)
            # GPIO.add_event_detect(self.GPIO_BP_STOP, GPIO.FALLING, callback=self.porte_stop, bouncetime=500)

            # Events sur fin course  haut/bas
            # GPIO.add_event_detect(self.GPIO_FC_B, GPIO.RISING, callback=self.porte_stop, bouncetime=400) 
            # GPIO.add_event_detect(self.GPIO_FC_H, GPIO.RISING, callback=self.porte_stop, bouncetime=400)

            # sortie output relais, ouvert par défaut
            GPIO.setup(self.GPIO_RL_1, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(self.GPIO_RL_2, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(self.GPIO_RL_3, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(self.GPIO_RL_4, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(self.GPIO_RL_5, GPIO.OUT, initial = GPIO.HIGH)
            GPIO.setup(self.GPIO_RL_6, GPIO.OUT, initial = GPIO.HIGH)

            # Detecteur de mouvement
            # GPIO.setup(self.GPIO_MVT, GPIO.IN)
            # GPIO.add_event_detect(self.GPIO_MVT , GPIO.BOTH, callback=self.detection_mvt)

            time.sleep(.5)
            logging.debug("- Init GPIO OK")

        except IOError as e:
            logging.info(e)
            sys.exit("ERREUR init GPIO")

        # -------------------------------------------
        # Init de l'écran
        '''
        try:
            logging.debug("- Init écran...") 
            self.ecran = epd1in54_V2.EPD()
            self.ecran.init()
            self.ecran.Clear(255) # 0: Black, 255: White
            time.sleep(1)
            logging.debug("- Init écran OK") 
        except IOError as e:
            self.ecran.Clear(255)
            sys.exit("ERREUR init écran: {}".format(e))

        # Police de caractère
        font = ImageFont.truetype(os.path.join(self.PICDIR, 'Font.ttc'), 18)

        # Définition de la zone statique
        image = Image.new(mode='1', size=(self.ecran.width, self.ecran.height), color=255)
        img = Image.open(os.path.join(self.PICDIR, 'poule.jpg'))
        image.paste(img, (50,100))
        draw = ImageDraw.Draw(image)
        self.ecran.displayPartBaseImage(self.ecran.getbuffer(image))


        # try: 
        draw.rectangle((5, 5, 195, 195), fill = 255)
        draw.text((50, 5), "Poulailler 2.0", font=font, fill=0, align='center')
        draw.text((10, 25), time.strftime('%H:%M'), font = font, fill = 0, align='left')
        draw.text((10, 45), "Levé soleil", font = font, fill = 0)
        draw.text((10, 65), "couché soleil", font = font, fill = 0)
        # except (RuntimeError, TypeError, NameError):
        #    pass
        
        self.ecran.display(self.ecran.getbuffer(image))
        '''

    # -------------------------------------------
    # Destructeur
    def __del__(self):
        '''
        try: 
            GPIO.cleanup()
        except RuntimeWarning:
            pass
        '''

    # -------------------------------------------
    # Actionneurs
    # -------------------------------------------

    '''
    def actionne(self, action):

        logging.debug("ACTIONNE action={}".format(action))

        # action identique  on ne fait rien
        if action  == self.ACTION:
            return 

        

        # Si le moteur tourne deja, on l'arrete
        # if (action == -1 or action == 1) and self.ACTION != 0:
        if GPIO.input(self.GPIO_RL_1) ==  GPIO.LOW:
            GPIO.output(self.GPIO_RL_1, GPIO.HIGH)
            time.sleep(.25)

        self.ACTION = action

        # Descente
        if action == -1:
            logging.debug("Set relais descente")
            GPIO.output(self.GPIO_RL_2, GPIO.HIGH)
            GPIO.output(self.GPIO_RL_3, GPIO.HIGH)
            time.sleep(.5)
            logging.debug("Set relais moteur ON")
            GPIO.output(self.GPIO_RL_1, GPIO.LOW)
            
            # On attend la fin de la descente, ou le timeout
            channel = GPIO.wait_for_edge(self.GPIO_FC_B, GPIO.RISING, timeout=10000)
            if channel is None:
                sys.exit('Timeout descente')
            else:
                logging.info("Arret moteur")
                GPIO.output(self.GPIO_RL_1, GPIO.HIGH)

            return

        
        # Montee
        elif action == 1:
            logging.debug("Set relais montee")
            GPIO.output(self.GPIO_RL_2, GPIO.LOW)
            GPIO.output(self.GPIO_RL_3, GPIO.LOW)
            time.sleep(.5)
            logging.debug("Set relais moteur ON")
            GPIO.output(self.GPIO_RL_1, GPIO.LOW)

            # On attend la fin de la descente, ou le timeout
            channel = GPIO.wait_for_edge(self.GPIO_FC_H, GPIO.RISING, timeout=10000)
            if channel is None:
                sys.exit('Timeout montee')
            else:
                logging.info("Arret moteur")
                GPIO.output(self.GPIO_RL_1, GPIO.HIGH)
            return

        
        # Arret
        elif action == 0:  
            logging.info("Arret moteur")
            GPIO.output(self.GPIO_RL_1, GPIO.HIGH)
    '''
        

    def porte_ouvre(self, pin = None):

        logging.debug("OUVRE Evenement sur pin {}".format(pin))
        
        # Position en erreur
        state = self.porte_etat()
        if state == self.STATE_ERR:
            logging.error("Erreur position porte: les 2 contacteurs de position sont actionnés")
            return False

        # porte déja ouverte ? On ne fait rien
        if state == self.STATE_OPEN:
            logging.info("Porte deja ouverte")
            return True

        logging.info("▲ Debut montée")
        
        logging.debug("Set relais montee")
        GPIO.output(self.GPIO_RL_2, GPIO.LOW)
        GPIO.output(self.GPIO_RL_3, GPIO.LOW)
        time.sleep(.5)
        logging.debug("Set relais moteur ON")
        GPIO.output(self.GPIO_RL_1, GPIO.LOW)

        # On attend la fin de la descente, ou le timeout
        time.sleep(0.05)
        channel = GPIO.wait_for_edge(self.GPIO_FC_H, GPIO.RISING) # , timeout=10000)
        if channel is None:
            return False
        else:
            logging.info("✖ Fin course Haut: Arret moteur")
            GPIO.output(self.GPIO_RL_1, GPIO.HIGH)
        
        return True

   
        
    def porte_ferme(self, pin=None):

        logging.info("FERME Evenement sur pin {}".format(pin))

        # Position en erreur
        state = self.porte_etat()
        if state == self.STATE_ERR:
            logging.error("Erreur position porte: les 2 contacteurs de position sont actionnés")
            return False

        # porte déja fermee ? On ne fait rien
        if state == self.STATE_CLOSED:
            logging.info("Porte déja fermée")
            return True

        logging.info("▼ Debut descente")

        logging.debug("Set relais descente")
        GPIO.output(self.GPIO_RL_2, GPIO.HIGH)
        GPIO.output(self.GPIO_RL_3, GPIO.HIGH)
        time.sleep(.5)
        logging.debug("Set relais moteur ON")
        GPIO.output(self.GPIO_RL_1, GPIO.LOW)
        
        # On attend la fin de la descente, ou le timeout
        time.sleep(0.05)
        etat = GPIO.wait_for_edge(self.GPIO_FC_B, GPIO.RISING) # , timeout=10000)
        if etat is None:
            return False 
        else:
            logging.info("✖ Fin course bas: Arret moteur")
            GPIO.output(self.GPIO_RL_1, GPIO.HIGH)
        return True



    def porte_stop(self, pin = None):
        
        logging.debug("STOP Evenement sur pin {}".format(pin))

        logging.info("✖ Btn STOP > Arret moteur")
        GPIO.output(self.GPIO_RL_1, GPIO.HIGH)

        
    # Position de la porte
    # 1: ouverte
    # 0: fermée
    # -1: entre-deux
    # -2: Etat schrödinger (ouverte & fermee en mm tps)
    def porte_etat(self):
        
        fc_h =  GPIO.input(self.GPIO_FC_H) # fin course haut
        fc_b =  GPIO.input(self.GPIO_FC_B) # fin course bas
        # erreur
        if fc_h == 1 and fc_b == 1:
            return self.STATE_ERR
        # Milieu
        elif fc_h == 0 and fc_b == 0:
            return self.STATE_MID
        # Ouverte
        elif fc_h == 1 and fc_b == 0:
            return self.STATE_OPEN
        # Fermee 
        elif fc_h == 0 and fc_b== 1:
            return self.STATE_CLOSED
        # erreur par défaut
        return self.STATE_ERR


    # -------------------------------------------
    # Gestion du temps
    # -------------------------------------------

    # Est-ce qu'il fait jour ? 
    # @return bool True=jour, Flase=nuit
    def is_jour(self):        
        
        city = LocationInfo(self.LOC_VILLE, 
            self.LOC_PAYS, 
            self.LOC_TZ, 
            self.LOC_COORD[0], self.LOC_COORD[1])
        
        s = sun(city.observer, tzinfo=city.timezone)


        time_now = utc.localize(datetime.datetime.now())
        return (bool)(s["sunrise"] < time_now and time_now < s["sunset"]) 



    # Action à faire au lancement
    def load(self):

        state = self.porte_etat()
        is_jour = self.is_jour()

        logging.debug("Etat porte {}".format(state))

        # Position en erreur
        if state == self.STATE_ERR:
            sys.exit("Erreur position porte: les 2 contacteurs de position sont actionnés")
        
        # On défini l'état de la porte au lancement
        # jour et porte fermée ou au milieu: On l'ouvre
        if True ==  is_jour and state != self.STATE_OPEN:
            logging.info("Jour et porte non ouverte -> Je l'ouvre")
            etat = self.porte_ouvre()
        
        # Nuit et porte ouverte
        elif False == is_jour and state != self.STATE_CLOSED:
            logging.info("Nuit et porte non ouverte -> Je la ferme")
            etat = self.porte_ferme()
        
        # OK, jour et porte ouverte
        elif True == is_jour and state == self.STATE_OPEN:
            logging.info('Jour et porte ouverte -> OK')
        
        # OK, nuit et porte fermee
        elif False == is_jour and state == self.STATE_CLOSED:
            logging.info('Nuit et porte fermee -> OK')
        else:
            logging.debug("Etat bizare ?!?")
        
        ## Attente si action précédente
        '''
        if self.ACTION != 0:
            logging.info("Attente fin de l'action en cours")
            while self.ACTION != 0:
                logging.debug("ATTENTE ACTION {}".format(self.ACTION))
                time.sleep(1)
        '''

        logging.debug("Demarrage programme principal")
        old_etat = self.is_jour()
        while True:                   
            is_jour = self.is_jour()

            if is_jour != old_etat:
                if is_jour == True:
                    logging.info("Cocorico, il fait jour !")
                    self.porte_ouvre()
                else:
                    logging.info("ZZzzz, c'est l'heure de dormir !")
                    self.porte_ferme()

            
            # On vérifie toutes les minutes l'état du soleil:
            time.sleep(60)   # attente minute 
            old_etat = is_jour



    def detection_mvt(self, channel):
        if GPIO.input(channel):     # if port 25 == 1  
            logging.debug("Mouvement detecté sur port {}".format(channel))  
        else:                  # if port 25 != 1  
            logging.debug("Absence mouvement sur port {}".format(channel))  
        # logging.debug('Mouvement detecté! {}'.format(channel))


# On gère un cleanup propre
def handler(signal_received, frame):
    exit("Interruption du programme")

if __name__ == '__main__':
    # On prévient Python d'utiliser la method handler quand un signal SIGINT est reçu
    signal(SIGINT, handler)
    p = Poulailler()
    try:    
        p.load()
    except SystemExit as e:
        logging.error("Sortie anormale: {}".format(e))
        GPIO.cleanup()
        


