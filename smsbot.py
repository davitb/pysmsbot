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
        self.sock.settimeout(1.0)            


    def send(self, msg):
        num_bytes = self.sock.send(msg)
        print "Sent bytes: {}".format(num_bytes)
        return num_bytes

    def readIntoBuffer(self):
        alldata = ""
        bytes_recd = 0
        MSGLEN = 10 * 4096
        IGNORE_LEN = 1544
        while True:
            try:
                data = self.sock.recv(MSGLEN)
            except Exception as e:
                break

            bytes_recd = bytes_recd + len(data)
            print "{}".format(bytes_recd)
            if not data or bytes_recd == 0: break

            alldata += data

            # if (bytes_recd == IGNORE_LEN):
            #     bytes_recd = 0
            #     alldata = ""
            #     continue

            print "Step: {}".format(self.step)
            if (self.step <= 1):
                break

            if (bytes_recd < MSGLEN):
                continue

        print "Received bytes: {}".format(bytes_recd)        
        return alldata

    def read(self):
        return self.readIntoBuffer()

    def close(self):
        if (self.sock != None):
            self.sock.shutdown(socket.SHUT_RDWR)
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
        account_sid = "AC4bea4553db1bfc1fa56731a958954e6c"
        auth_token  = "8e99471f0a134d830f8d28442da25829"
        self.client = TwilioRestClient(account_sid, auth_token)
        self.finalReceivedData = ""

    def sendSMS(self, to, msg, from_):
        try:
             
            self.client.messages.create(body=msg, to=to, from_=from_)
            #print "To be sent: " + msg

        except twilio.TwilioRestException as e:
            print e

    def getTunnel(self):
        return self.tunnel

    def connect(self):
        self.close()
        self.tunnel.connect()
        self.receivingThread.start()

    def close(self):
        if (self.tunnel.close() == True):
            self.stopThread = True
            self.receivingThread.join()
            self.receivingThread = threading.Thread(target=self.receivingWorker)
            self.stopThread = False

    def sendSmsInChunks(self, msg):

        parser = SmsProtocolParser()
        n = 100 # 160/2 - 2 - 1, 1 byte redundant
        chunks = [msg[i:i + n] for i in range(0, len(msg), n)]

        for i, val in enumerate(chunks):
            chunk = parser.encodeChunk(val, len(chunks), i)
            print chunk
            self.sendSMS("4084390019", chunk, "16506238842") 
            time.sleep(0.2)

    def receivingWorker(self):

        while self.stopThread == False:
            try:
                read_bytes = self.tunnel.read()
            except Exception as e:
                break

            if (len(read_bytes) == 0):
                continue

            #print binascii.hexlify(bytearray(read_bytes))
            self.sendSmsInChunks(read_bytes)

        print "Receiver stopped"



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
        return "r" + format(all, '02x') + format(index, '02x') + binascii.hexlify(bytearray(val))

sshSms = SSHSMSHandler()
parser = SmsProtocolParser()

@app.route('/ssh', methods=['GET', 'POST'])
def ssh():
    global sshSms
    global parser

    try:
        # print "From " + request.values.get('From', None)
        # print "To " + request.values.get('To', None)
        # print "Body " + request.values.get('Body', None)
        # print "---------------\n"

        message = request.values.get('Body', None).encode("utf-8")
        print message
        if (not parser.setNextChunk(message)):
            return "still receiving"

        opCode, message = parser.getFinalData()
        parser.reset()

        print "final message: " + message
        
        if (opCode == 'n'): # connect
            sshSms.connect()
            # sshSms.getTunnel().send("SSH-2.0-TrileadSSH2Java_213\r\n") 
        elif (opCode == 'l'): # close
            sshSms.close()
        elif (opCode == 's'): # send
            sshSms.getTunnel().incrStep()
            message = message.decode("hex")
            sshSms.getTunnel().send(message) 

        return "success"
    except Exception as e:
        print('*** Failed: ' + str(e))
        traceback.print_exc()


if __name__ == "__main__":
    app.run(debug=True)

