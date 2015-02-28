from flask import Flask, request, render_template
from twilio.util import TwilioCapability
import twilio.twiml
import socket
import sys
import traceback
import json
import base64
import binascii

app = Flask(__name__)

class SSHTunnelClient:

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.step = 0

    def incrStep(self):
        self.step = self.step + 1

    def connect(self, host = "52.1.138.230", port = 22):
        self.sock.connect((host, port))
        self.sock.setblocking(0)
        self.sock.settimeout(0.2)            


    def send(self, msg):
        num_bytes = self.sock.send(msg)
        print "Sent bytes: {}".format(num_bytes)
        return num_bytes

    def readIntoBuffer(self):
        alldata = ""
        bytes_recd = 0
        MSGLEN = 10 * 4096
        while True:
            try:
                data = self.sock.recv(MSGLEN)
            except Exception as e:
                break

            bytes_recd = bytes_recd + len(data)
            print "{}".format(bytes_recd)
            if not data: break

            alldata += data

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
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


tunnel = SSHTunnelClient()
tunnel.connect()
keepReceiving()

counter = 0

def sendSMS(to, msg, from):
    try:
        account_sid = "AC4bea4553db1bfc1fa56731a958954e6c"
        auth_token  = "8e99471f0a134d830f8d28442da25829"
        client = TwilioRestClient(account_sid, auth_token)
         
        return client.messages.create(body=msg, to=to, from_=from)

    except twilio.TwilioRestException as e
        print e
        return ""

def keepReceiving:

    while True
        try:
            read_bytes = tunnel.read()
        except Exception as e:
            print "Receiving stopped"
            break

        n = 80
        chunks = [read_bytes[i:i+n] for i in range(0, len(read_bytes), n)]
        for chunk in chunks:
            sendSMS("4084390019", encodeForSending(chunk), "16506238842")


def encodeForSending(msg):
    return json.dumps({ "op" : "r", "msg": binascii.hexlify(bytearray(msg)) })

@app.route('/ssh', methods=['GET', 'POST'])
def ssh():
    global tunnel
    global counter

    try:
        print "From " + request.values.get('From', None)
        print "To " + request.values.get('To', None)
        print "Body " + request.values.get('Body', None)
        print "---------------\n"
        
        counter += 1
        message = "".join(["dodo", " has messaged ", request.values.get('To'), " ", str(counter), " times."])
        resp = twilio.twiml.Response()
        resp.sms(message)
     
        print str(resp)

        return str(resp)

        message = request.values.get('msg', None).encode("utf-8")
        print message
        message = json.loads(message)
        
        opType = message['op']
        if (opType == 's'):        
            tunnel.incrStep()
            message = message['msg'].encode("utf-8").decode("hex")
            sent_bytes = tunnel.send(message)
            return json.dumps({ "op" : "s", "msg": sent_bytes })

        else:
            read_data = tunnel.read()
            return json.dumps({ "op" : "r", "msg": binascii.hexlify(bytearray(read_data)) })

    except Exception as e:
        print('*** Failed: ' + str(e))

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    app.run(debug=True)

