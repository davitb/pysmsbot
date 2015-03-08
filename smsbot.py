from flask import Flask, request, render_template
from twilio.util import TwilioCapability
from twilio.rest import TwilioRestClient
import twilio.twiml
import socket
import sys
import traceback
import json
import base64
import binascii
import threading
import time
import os
import random

receivedSmsCounter = 0
#twilio_num = "16692227897"
twilio_nums = ["14083594145", 
               "14086693027", 
               "14086693024",
               "14083594050"]

davit_num = "14084390019"
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token  = os.environ.get('TWILIO_AUTH_TOKEN')

if (account_sid == None or auth_token == None):
    print "Twilio account not setup"
    sys.exit()

app = Flask(__name__)

class SSHTunnelClient:

    def __init__(self):
        self.sock = None
        self.step = 0

    def incrStep(self):
        self.step = self.step + 1

    def connect(self, host = "52.1.138.230", port = 22):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.setblocking(0)
        self.sock.settimeout(0.7)            


    def send(self, msg):
        num_bytes = self.sock.send(msg)
        print "Sent bytes: ", num_bytes
        return num_bytes

    def read(self):
        alldata = ""
        bytes_recd = 0
        MSGLEN = 10 * 4096
        IGNORE_LEN = 1544
        while True:
            try:
                data = self.sock.recv(MSGLEN)
            except Exception as e:
                break

            bytes_recd += len(data)
            print bytes_recd
            if not data or bytes_recd == 0: 
                raise Exception("Socket closed")

            alldata += data

            # This is a workaround
            print "Step: ", self.step
            if (self.step <= 1):
                break

            if (bytes_recd < MSGLEN):
                continue

        print "Received bytes: ", bytes_recd
        return alldata

    def close(self):
        if (self.sock != None):
            #self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.sock = None
            return True
        return False

class SSHSMSHandler:

    def __init__(self):
        self.tunnel = SSHTunnelClient()
        self.counter = 0
        self.stopThread = False
        self.receivingThread = threading.Thread(target=self.receivingWorker)
        self.client = TwilioRestClient(account_sid, auth_token)
        self.finalReceivedData = ""
        self.sentSmsCounter = 0
        self.nextNumber = 0

    def sendSMS(self, to, msg, from_):
        try:
             
            self.sentSmsCounter += 1
            self.client.messages.create(body=msg, to=to, from_=from_)
            # print "To be sent over SMS: " + msg

        except twilio.TwilioRestException as e:
            print e

    def getTunnel(self):
        return self.tunnel

    def connect(self, hostname):
        self.close()
        self.tunnel.connect(host = hostname)
        self.receivingThread.start()

    def close(self):
        print "Total number of sent SMS: ", self.sentSmsCounter
        self.sentSmsCounter = 0
        if (self.tunnel.close() == True):
            self.stopThread = True
            self.receivingThread.join()
            self.receivingThread = threading.Thread(target=self.receivingWorker)
            self.stopThread = False

    def sendSmsInChunks(self, msg):

        parser = SmsProtocolParser()
        msg = base64.urlsafe_b64encode(msg)
        n = 155 # 160 - 5, 1 byte redundant
        chunks = [msg[i:i + n] for i in range(0, len(msg), n)]

        for i, val in enumerate(chunks):
            chunk = parser.encodeChunk(val, len(chunks), i)
            print chunk
            self.sendSMS(davit_num, chunk, self.getNextTwilioNumber()) 
            time.sleep(0.1)

    def receivingWorker(self):

        while self.stopThread == False:
            try:
                read_bytes = self.tunnel.read()
            except Exception as e:
                # Socket closed
                print "Socket closed"
                break

            if (len(read_bytes) == 0):
                continue

            self.sendSmsInChunks(read_bytes)

        print "Receiver stopped"

    def getNextTwilioNumber(self):
        self.nextNumber += 1
        if (self.nextNumber == len(twilio_nums)):
            self.nextNumber = 0
        print "sending from: " + twilio_nums[self.nextNumber]
        return twilio_nums[self.nextNumber]


class SmsProtocolParser:

    def __init__(self):
        self.reset()

    def setNextChunk(self, nextChunk):
        # An SMS message has the following format
        # OpCode (1 byte, string), NumOfAllChunks (1 byte, hex encoded string), 
        # Index (1 byte, hex encoded string), Message (N bytes, hex encoded)

        self.chunks.append(nextChunk)

        self.numOfReceivedChunks += 1
        numOfOverallChunks = int(nextChunk[1:3], 16)
        if (self.numOfReceivedChunks == numOfOverallChunks):
            return True

        print "long SMS message"
        return False

    def getFinalData(self):
        opCode = self.chunks[0][0]
        sortedChunks = sorted(self.chunks, key = lambda chunk: int(chunk[3:5], 16))
        return opCode, ''.join(e[5:] for e in sortedChunks)

    def reset(self):
        self.chunks = []
        self.numOfReceivedChunks = 0

    def encodeChunk(self, val, all, index):
        return "r" + format(all, '02x') + format(index, '02x') + val

sshSms = SSHSMSHandler()
parser = SmsProtocolParser()

@app.route('/ssh', methods=['GET', 'POST'])
def ssh():
    global sshSms
    global parser
    global receivedSmsCounter

    try:
        # print "From " + request.values.get('From', None)
        # print "To " + request.values.get('To', None)
        # print "Body " + request.values.get('Body', None)
        # print "---------------\n"

        receivedSmsCounter += 1
        message = request.values.get('Body', None).encode("utf-8")
        print message
        if (not parser.setNextChunk(message)):
            return "still receiving"

        opCode, message = parser.getFinalData()
        parser.reset()

        print "final message: " + message
        
        if (opCode == 'n'): # connect
            # message is the hostname
            sshSms.connect(message)
            #sshSms.getTunnel().send("SSH-2.0-TrileadSSH2Java_213\r\n") 
        elif (opCode == 'l'): # close
            print "Total number of received SMS: ", receivedSmsCounter
            receivedSmsCounter = 0
            sshSms.close()
        elif (opCode == 's'): # send
            sshSms.getTunnel().incrStep()
            # message = message.decode("hex")
            message = base64.urlsafe_b64decode(message)
            sshSms.getTunnel().send(message) 

        return "success"
    except Exception as e:
        print('*** Failed: ' + str(e))
        traceback.print_exc()

if __name__ == "__main__":
    app.run(host="0.0.0.0")

