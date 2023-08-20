/*
 * Copyright 2023 Mark Duffield
 *
 * Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file
 * except in compliance with the License. A copy of the License is located at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0 
 *
 * or in the "license" file accompanying this file. This file is distributed on an "AS IS"
 * BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under the License.
 */

import dotenv from 'dotenv';
dotenv.config();

import * as fs from 'fs';
import express from 'express';
import bodyParser from 'body-parser';
import session from 'express-session';

const RUNTIME_ENV = process.env.NODE_ENV || 'development';

const app = express()
const securePort = 3030;
app.use(bodyParser.urlencoded({ extended: true }));

let https;
try {
  https = await import('node:https');
} catch (err) {
  console.error('https support is disabled!');
}

app.use(session({
  secret: 'keyboard cat',
  resave: false,
  saveUninitialized: true,
  cookie: {
    secure: true,
    httpOnly: true,
  }
}))

app.route('/')
  .get((req, res) => {
    res.setHeader('Content-type', 'text/html');
    res.write(
    ` <!DOCTYPE html> 
      <html><head><title>Session example</title></head><body>
      <div style="text-align:center; margin: 0 auto; max-width: 550px;">
        <br><br>
        <h3>Session (cookies) example</h3>
          <p>
            This is an example of a session. You should see a "Secure" 
            and "HttpOnly" cookie set for this page, and when you enter 
            a word it will be stored with the session. If you delete the 
            cookie, the session information and the word you entered 
            will be deleted.
          </p>
        <form action="/" method="POST">
          <input type="text" name="anyword">
          <button type="submit">Submit</button>
        </form> 
        <br>`
    );
    res.write('Entered word: <b>' + (req.session.anyword || 'no word entered') + '</b>');
    res.write('</div></body> </html>')
    res.status(200).send();
  })
  .post((req, res) => {
    req.session.anyword = req.body.anyword;
    res.status(302).redirect('/');
  })

let keyDirectory = process.env.LOCAL_KEY_DIR;
if (RUNTIME_ENV === 'production') {
  keyDirectory = '/home/webapp/appCert/';
} 

const appKeyName = process.env.APP_KEY_FILE || 'app1.key';
const appCertName = process.env.APP_CERT_FILE || 'app1.crt';
const httpsOptions = {
  key: fs.readFileSync(keyDirectory + appKeyName),
  cert: fs.readFileSync(keyDirectory + appCertName),
  passphrase: process.env.PKEY_PASSPHRASE 
}

const httpsServer = https.createServer(httpsOptions, app)
  .listen(process.env.PORT || securePort, () => {
    console.log('https server started on port ' + 
     httpsServer.address().port + ' running in ' + RUNTIME_ENV);
  })
