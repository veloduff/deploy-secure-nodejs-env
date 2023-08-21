---
toc_depth: 3
hide:
  - navigation
---

# Deploy a secure Node.js app in a dev environment 

There are several options for launching a Node.js dev environment for web applications. For this guide, I'll be using AWS Elastic Beanstalk. The security and knowing what region my data is in, are enough reasons to choose Beanstalk. That said, there are some extra steps that we'll have to take to launch an inexpensive dev environment on Beanstalk. My goal is to keep cost to nothing, or less than $5/month. You can also think about using Amplify, but this guide is using Node.js without React. 

This guide illustrates the process of launching a secure Node.js application environment, while also minimizing cost (but it is not intended for production). The environment **should** not cost more then $6/month, and will probably be around $3.50/month. Please ensure that you using an instance that will meet your cost requirements.

In addition to this guide, I have created a README on the GitHub repo that performs the steps here, but using a setup command instead of running each command one at a time. Prior to using the setup command, you should at least read this guide to understand what is being done. Go to the [veloduff/deploy-secure-nodejs-env](https://github.com/veloduff/deploy-secure-nodejs-env) repo for more information about using the setup command.

## Security in mind 

It can be very convenient to initially approach projects without consideration for security. For example, using plain text to store passwords or using http instead of https. Rather than having to refactor to meet security requirements later on, I prefer to start with at least some security measures in place already. This is not the easy road, and it is certainly the path less chosen. So if you find yourself spending hours upon hours trying to debug why a cert won't load (bad characters), or why an instance isn't reachable (wrong security group), or why the reverse proxy settings aren't loading (change from AL1 to AL2), you will have found that you are not alone. Security is hard, and not for the weary. With that said, the numerous "extra" steps here that you may not want to do will build a secure and inexpensive development environment for running Node.js apps.

## Prerequisites 

We will be using the Elastic Beanstalk command line utility, rather than the AWS Console. It is assumed that you have installed the `eb` command line utility. Details and instructions can be found here: [Install the EB CLI](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3-install.html). You will also need to [configure AWS CLI access](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html). It is also assumed that you have the node development tools installed, as well as `git`.

#### Security starting at the application layer

The approach that I have taken here is to use `https` at the application layer. Specifically, rather than using `http.createServer` (which in express is the same as `app.listen`, [reference here](https://expressjs.com/en/5x/api.html#app.listen)) we'll be using `https.createServer` (note the http**s**). This means that we will have to use SSL certificates (although they will be self-signed) to secure the connection from the browser all the way to the application, and not just to the web server (or reverse proxy in this case).

## Deployment strategy and overview 

As we will not be using production features (e.g., Load Balancer, backups, managed updates), this environment that we are setting up is intended to be used for development purposes. To minimize cost we'll be using a single instance (no Load Balancer) Beanstalk environment running on a spot instance ([more info on EC2 Spot Instances](https://aws.amazon.com/ec2/spot/)). The environment **should** not cost more then $6/month, and will probably be around $3.50/month. Please ensure that you are using an instance that will meet your cost requirements. 

To deploy a secure Node.js development environment on Beanstalk, we'll need to:

  * Have an application to deploy that uses https (at the application layer) - I have provided an example app
  * Create two sets of self-signed SSL keys and certificates (one for the web server and one for the application)
  * Create the configuration files for both the Beanstalk environment and the Nginx reverse proxy
  * Create a single instance Beanstalk environment using EC2 Spot 

## How does Beanstalk deploy

It is useful to understand both how deployment with Beanstalk happens and what will be included in the deployment. Throughout the process of attempting to deploy environments, I struggled because I did not understand why my changes and updates were not being deployed.

Beanstalk deployments are dependent on whether or not you are using `.gitignore` and `.ebignore`. For now, let's assume that you are not using a `.ebignore` file, but you do have a `.gitignore` (which is probably the most common dev environment). In this scenario, Beanstalk will only deploy changes that have been either **staged** or **committed** in your git repo. In other words, **Beanstalk uses the git status to deploy your applications**. The Beanstalk documentation describes this best:

From: [Using the EB CLI with Git (Deploying changes)](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb3-cli-git.html#eb3-cli-git.deploy)
> **Deploying changes**
>
> By default, the EB CLI deploys the latest commit in the current branch, using the commit ID and message as the application version label and description, respectively. If you want to deploy to your environment without committing, you can use the --staged option to deploy changes that have been added to the staging area.

What this means, is that if you make a change without staging **AND** committing the change, it will not be included in the next deployment. That said, from the documentation you can see that the changes can be included by only staging (i.e., `git add .`), and then using the command `eb deploy --staged`. 

Another important part of deployment, is whether or not you have a `.ebignore` file in your project root.

From: [Configure the EB CLI (Ignoring files using .ebignore)](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3-configuration.html#eb-cli3-ebignore)
> You can tell the EB CLI to ignore certain files in your project directory by adding the file .ebignore to the directory. This file works like a .gitignore file. When you deploy your project directory to Elastic Beanstalk and create a new application version, the EB CLI doesn't include files specified by .ebignore in the source bundle that it creates.
>
> If .ebignore isn't present, but .gitignore is, the EB CLI ignores files specified in .gitignore. If .ebignore is present, the EB CLI doesn't read .gitignore.
> 
> When .ebignore is present, the EB CLI doesn't use git commands to create your source bundle. This means that EB CLI ignores files specified in .ebignore, and includes all other files. In particular, **it includes uncommitted source files**.

There are two very important items to note from this: 
1. If `.ebignore` is present, the EB CLI doesn't read `.gitignore`. 
1. When `.ebignore` is present, the EB CLI doesn't use git commands to create your source bundle. This means that the EB CLI ignores files specified in `.ebignore`, and includes all other files. In particular, it includes uncommitted source files. Which is not case if **only** the `.gitignore` file exists.

With that said, the next steps will document how to setup a straightforward development environment that uses both the `.gitignore` and `.ebignore` files in the project's root directory.

## Using Beanstalk configuration files

Something that I didn't discover until I had already deployed several apps on Beanstalk, was [Advanced environment customization with configuration files (.ebextensions)](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/ebextensions.html). This allows you to use the `.ebextensions` folder at your project root directory for Beanstalk configuration files (with extension `.config`). From the docs:

> These configuration files are YAML- or JSON-formatted documents with a .config file extension that you place in a folder named .ebextensions and deploy in your application source bundle.
>
> For example here is a `.ebextensions/network-load-balancer.config` file from [Advanced environment customization with configuration files (.ebextensions)](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/ebextensions.html), that modifies a configuration option to set the type of your environment's load balancer to Network Load Balancer.
>
> ```sh
>  option_settings:
>    aws:elasticbeanstalk:environment:
>      LoadBalancerType: network
> ```

More information, including precedence, can be found here:  [Configuration options](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options.html).

Where you can, my suggestion is to use `<file>.config` files, rather than using command line options or using the AWS Console. This reduces the risk of setting options in more than one place, and also allows you to rebuild environments with the same configuration files.

You can use the `eb config --display` command to show the configuration, or make changes with `eb config`. You can also use existing (and customized) environments as a template (see [eb config](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb3-config.html)).

We will be using a file named `options.config` for Beanstalk configuration settings.

## Setup the project environment

You have the option of not using `git` at all, but as that is usually not the case, it's assumed that you will be using `git`. If you have not already, you should initialize your repo with git, here's an example:

```sh
$ git init -b main
$ echo "# My new repo" > README.md
$ git add .
$ git commit -m "initial commit"
```

#### Create the `.gitignore` and `.ebignore` files 

Now you need to setup the `.gitignore` and `.ebignore` files. My suggestion is to use a `.ebignore` file based on a `.gitignore` file that you would normally use for development. I have a catch-all `.gitignore` file that I copy to `.ebignore` and then I add Beanstalk files/dirs I want to ignore to my `.gitignore` file. In others words, use the `.gitignore` file you normally use for `.ebignore`, and then add Beanstalk files/dirs to your `.gitignore` file. 

Hopefully these steps help to clarify:
1. Copy an existing `.gitignore` file to the project root
1. Copy `.gitignore` to `.ebignore` 
1. Because the SSL keys and certs are stored in files that are in the `.ebextensions` directory, **you need to make sure that the `.gitignore` file includes the Beanstalk directories**, so your keys and certs are not included on a public facing repo. To do this, add the necessary Beanstalk specific dirs/files to the `.gitignore` file. For example, at the bottom of my `.gitignore` file, I add this:
   ```
   # Elastic Beanstalk
   .ebextensions/
   .elasticbeanstalk/
   .platform/
   ```

**NOTE**: It's important to remember **not** to include the above directories in the `.ebignore` file, otherwise the configuration files will not be included in the deployment.

#### More information on the deployment workflow

On the [Extending Elastic Beanstalk Linux platforms](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/platforms-linux-extend.html) page, look at the **"Instance deployment workflow"** for an illustrated introduction for how Beanstalk deployments work.

## Project structure

There will be several files and directories that we will be creating (in `.ebextensions` and other directories). There is an example project directory on the same page mentioned above, if you go to [Extending Elastic Beanstalk Linux platforms](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/platforms-linux-extend.html), and look under **"Application example with extensions"**. This has the extensions directory (`.ebextensions`) and the proxy configuration directory (`.platform`) as well.

For our project, here is the project structure that we will be using (there is nothing to create now, this is just for reference):
```sh
.
├── .ebextensions
│   ├── options.config
│   ├── sec-group.config
│   └── ssl-files.config
├── .ebignore
├── .elasticbeanstalk
│   └── config.yml
├── .env
├── .gitignore
├── .platform
│   └── nginx
│       ├── conf.d
│       │   └── https.conf
│       └── nginx.conf
├── app.js
├── package-lock.json
└── package.json
```

## Create SSL keys and certificates

Before we do the actual setup of the Beanstalk environment, and because we will be using SSL (https), we're going to first create the SSL key and certificate for the Nginx web server, and second, also create a cert/key for the app itself. By creating two different sets of certs, we are isolating resources. If the app cert is compromised, the web server cert is still safe, and vice versa. For the app cert, the user (e.g., webapp) running the app on the instance will need permissions to access the cert (directory and file permissions). Additionally, we will be using a pass phrase for the app cert. The pass phrase will be included in a Beanstalk environment variable, but can not be seen in the github repo (and we'll use `.env` for local testing and put `.env` in the `.gitignore file`).

We're going to use self-signed certificates, created with `openssl`.

The cert used for the web server will not have a pass phrase, because we want the web server to be able restart without having to enter the pass phrase. The application cert will have a pass phrase that we provide as part of the environment in Beanstalk, but the pass phrase will not be visible on the github repo.

### For the web server: Create a key and cert without using a pass phrase 

This command will generate an RSA private key file (saved in PEM format):

```sh
$ openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out myWebServerKey.pem 
..........................................................................++++
.....................................................................................................................++++
```

This next command will create the certificate request file (also in PEM format) using the key file just created. I'm using the domain `*.elasticbeanstalk.com` to remind me what the cert is intended for, but you should be able use any domain you want.

```sh
$ openssl req -x509 -new -sha256 -key myWebServerKey.pem -out myWebServerCertReq.pem -subj '/C=US/ST=California/L=SJC/O=MyOrg1/CN=*.elasticbeanstalk.com'
```

### For the application:  Create a key and cert using a pass phrase 

We'll use the `openssl` command to generate pass phrase, and save it to a file to avoid STDOUT (and avoid command line history and ps info):
```sh
$ openssl rand -base64 32 > pass_phrase.txt
```

This next command will generate an RSA private key file (saved in PEM format), using the pass phrase we just created as input:
```sh
$ openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -aes-256-cbc -pass file:pass_phrase.txt -out myAppKey1.pem
```

And now create the certificate request file (also in PEM format) using the key file we just created and the pass phrase file as input.
```sh
$ openssl req -x509 -new -sha256 -key myAppKey1.pem -passin file:pass_phrase.txt -out myAppCertReq1.pem -subj '/C=US/ST=California/L=SJC/O=MyApp1/CN=*.elasticbeanstalk.com'
```

**NOTE:** You will need these five files (two cert files, two key files, one pass phrase file) in later steps to build the `ssl-files.config` file.

## Setup local testing environment

For local testing, you'll need to setup a `.env` file (used by the dotenv package) with cert and key information to be used by your application. Make sure that `.env` is in your `.gitignore` file. In your project root, create the `.env` file with the pass phrase, the location of the application cert and key (which is in a directory you choose), and their file names on your local machine:

```sh
# location: .env (of project root)
PKEY_PASSPHRASE: '<pass_phrase_for_private_key>'
LOCAL_KEY_DIR = '../Certificates/'
APP_KEY_NAME = 'myAppKey1.pem'
APP_CERT_NAME = 'myAppCertReq1.pem'
```

## Test locally

In the interest of showing an end-to-end process, I am including the example code below. This is an app that will create a session (cookie) if the connection is using https from the browser to the app.

Here the are steps to create the app. First, initialize the node project with ES6 to support `type: module`, and then install needed packages:
```sh
$ npm init es6 -y
$ npm i express express-session dotenv body-parser
```

Create the `app.js` file with this:
```js
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
```

Test locally by using:
```
$ node app.js
```
And you should see the app running https://localhost:3030 (note the **https**)


## Initialize and deploy on Beanstalk

### Initialize the application 

We will be using the [Elastic Beanstalk command line](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3.html). Our next step is to initialize the application with `eb init` in the project root. The `eb init` command will ask several questions to setup the application, to include setting up your access and secret keys. Make sure that you are selecting the correct information (region, Node.js version, etc.)

Here is an example run:

```sh
$ eb init

Select a default region
1) us-east-1 : US East (N. Virginia)
2) us-west-1 : US West (N. California)
3) us-west-2 : US West (Oregon)
... (many regions omitted) ...
(default is 1): 3

Select an application to use
1) test-app-1 
2) [ Create new Application ]
(default is 2): 2

Enter Application Name
(default is "eb-testing-1"): eb-testing-app-1
Application eb-testing-app-1 has been created.

It appears you are using Node.js. Is this correct?
(Y/n):
Select a platform branch.
1) Node.js 18 running on 64bit Amazon Linux 2
2) Node.js 16 running on 64bit Amazon Linux 2
3) Node.js 14 running on 64bit Amazon Linux 2
(default is 1): 1

Do you wish to continue with CodeCommit? (Y/n): n
Do you want to set up SSH for your instances? (Y/n): y

```

You can also run the `eb init` command with arguments to answer some or all of the questions:
```sh
eb init -r us-west-2 -p node.js eb-testing-app-1 
```

### Configure your deployment 

We will be using several files to configure the Beanstalk environment. To be specific, and looking at the directory tree again, we'll be using these files for customization:

```sh
.
├── .ebextensions
│   ├── options.config
│   ├── sec-group.config
│   └── ssl-files.config
...
├── .platform
│   └── nginx
│       ├── conf.d
│       │   └── https.conf
│       └── nginx.conf
...
```

At your project root, create the directories for the configuration files:
```sh
$ mkdir .ebextensions
$ mkdir -p .platform/nginx/conf.d
```

Now we will go through the process of creating each file that will be used for deployment.

#### Create the `.ebextensions/options.config` file

For the `options.config` file, you'll need to add environment variables. Specifically:
1. The port number that your app will be running on.
1. The pass phrase for the application key file (the one from the `pass_phrase.txt` file above).
1. Set the `NODE_ENV` to `production`. Although this is a dev environment, this helps separate local development (dev) and running on Beanstalk (prod)
 
Here is the `.ebextensions/options.config` file:
```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    PORT: 5000
    PKEY_PASSPHRASE: '<pass_phrase_for_private_key>'
    NODE_ENV: 'production'
```

#### Create the `.ebextensions/ssl-files.config` file

This file instructs Beanstalk to create the SSL key and cert files on the instance that will be used by the Nginx reverse proxy and your application. For the template below, you will need to use the self-signed keys and certificates that you created to replace everything that is between the `-----BEGIN ...` and `-----END ...`.

The **web server** key and cert will be created in the directory `/etc/pki/tls/certs/` and owned by `root`. The **application** key and cert will be created in the directory `/home/webapp/appCert/` and owned by the user `webapp`. Both the keys and certificates are set to read only only by the owner (i.e., root or webapp).

**Alignment is very important and you have to use only spaces, not tabs.**

```yaml
# location: .ebextensions/ssl-files.config

files:

  /etc/pki/tls/certs/server.crt:
    mode: "000400"
    owner: root
    group: root
    content: |
      -----BEGIN CERTIFICATE-----
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF                                         sdfasdf08080
      ASASFWEASEF     WEB SERVER CERTIFICATE FILE HERE    sdfasdf08080
      ASASFWEASEF                                         sdfasdf08080
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF124508asdfa==
      -----END CERTIFICATE-----
      
  /etc/pki/tls/certs/server.key:
    mode: "000400"
    owner: root
    group: root
    content: |
      -----BEGIN PRIVATE KEY-----
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF                                         sdfasdf08080
      ASASFWEASEF    WEB SERVER PRIVATE KEY FILE HERE     sdfasdf08080
      ASASFWEASEF                                         sdfasdf08080
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF124508asdfa==
      -----END PRIVATE KEY-----

  /home/webapp/appCert/app1.crt:
    mode: "000400"
    owner: webapp
    group: webapp 
    content: |
      -----BEGIN CERTIFICATE-----
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF                                          dfasdf08080
      ASASFWEASEF     APPLICATION CERTIFICATE FILE HERE    dfasdf08080
      ASASFWEASEF                                          dfasdf08080
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF124508asdfa==
      -----END CERTIFICATE-----

  /home/webapp/appCert/app1.key:
    mode: "000400"
    owner: webapp
    group: webapp 
    content: |
      -----BEGIN ENCRYPTED PRIVATE KEY-----
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF                                          dfasdf08080
      ASASFWEASEF    APPLICATION PRIVATE KEY FILE HERE     dfasdf08080
      ASASFWEASEF                                          dfasdf08080
      ASASFWEASEF124508asdfaASDF12508125asdfasdf082531808asdfasdf08080
      ASASFWEASEF124508asdfa==
      -----END ENCRYPTED PRIVATE KEY-----
```

#### Create the `.ebextensions/sec-group.config` file

The `.ebextensions/sec-group.config` file is used to open port 443 on the instance, update the `CidrIp` to restrict access to a specific IP or CIDR block:

```yaml
# location: .ebextensions/sec-group.config 
Resources:
  sslSecurityGroupIngress: 
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: {"Fn::GetAtt" : ["AWSEBSecurityGroup", "GroupId"]}
      IpProtocol: tcp
      ToPort: 443
      FromPort: 443
      CidrIp: 0.0.0.0/0
```

#### Create the `.platform/nginx/conf.d/https.conf` file

**A note about the https configuration**

The configurations templates that I am using are found in the official AWS Elastic Beanstalk documentation: [Configuring your application to terminate HTTPS connections at the instance](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/https-singleinstance.html). The config file to setup https on a single instance will need the file location, syntax, and the `listen` line to be updated, which I found on the re:Post article [How do I configure an SSL certificate for an application running in an Elastic Beanstalk environment?](https://repost.aws/knowledge-center/elastic-beanstalk-ssl-configuration) in the section **Terminate HTTPS at instance level**. That same article also does a great job of explaining the move from AL1 to AL2.

**NOTE:** There is a difference between using Amazon Linux 1 and Amazon Linux 2. When configuring the Nginx reverse proxy, the location for files that are used to extend the Nginx configuration has moved to `.platform/nginx/conf.d/`. If you want to completely replace the Nginx configuration then you use `.platform/nginx/nginx.conf` (which we will be doing). More details can be found in the section **"Configuring nginx"** in [Extending Elastic Beanstalk Linux platforms](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/platforms-linux-extend.html), and also [Migrating your Elastic Beanstalk Linux application to Amazon Linux 2](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features.migration-al.html).

We configure Nginx to listen on port 443, by creating the `.platform/nginx/conf.d/https.conf` with the config info below. `proxy_pass` has to point to `https` and we need to use the port number that we used for `PORT` in the `options.config` file we created above. This configures Beanstalk to use port **5000** to run your application. In your application you do not need to hard-code the port number, you can use, for example: `process.env.PORT || 3030`.

Here is the entire `.platform/nginx/conf.d/https.conf` you should use:

```conf
# HTTPS server
# location: .platform/nginx/conf.d/https.conf

server {
  listen       443 ssl;
  server_name  localhost;

  ssl_certificate      /etc/pki/tls/certs/server.crt;
  ssl_certificate_key  /etc/pki/tls/certs/server.key;

  ssl_session_timeout  5m;

  ssl_protocols  TLSv1 TLSv1.1 TLSv1.2;
  ssl_prefer_server_ciphers   on;

  location / {
          ## proxy_pass has to point to https and the port number used for PORT in the options.conf file
          proxy_pass  https://localhost:5000;
          proxy_set_header   Connection "";
          proxy_http_version 1.1;
          proxy_set_header        Host            $host;
          proxy_set_header        X-Real-IP       $remote_addr;
          proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header        X-Forwarded-Proto https;
  }
}
```

#### Create the `.platform/nginx/nginx.conf` file

For the redirect to work after initial deployment, edit the main Nginx conf file (`.platform/nginx/nginx.conf`). I added an https redirect from port 80. Specifically, I added this to the server listening on port 80:

```conf
        # Permanently redirecting to https
        return 301 https://$host$request_uri;
```

This is has resulted in a predicable environment launching, with the redirect to https working. Here is the entire `.platform/nginx/nginx.conf` file:

```conf
# Elastic Beanstalk Nginx Configuration File
# Added redirect
# location .platform/nginx/nginx.conf

user                    nginx;
error_log               /var/log/nginx/error.log warn;
pid                     /var/run/nginx.pid;
worker_processes        auto;
worker_rlimit_nofile    31486;

events {
    worker_connections  1024;
}

http {
    server_tokens off;

    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    include       conf.d/*.conf;

    map $http_upgrade $connection_upgrade {
        default     "upgrade";
    }

    server {
        listen        80 default_server;
        access_log    /var/log/nginx/access.log main;

        client_header_timeout 60;
        client_body_timeout   60;
        keepalive_timeout     60;
        gzip                  off;
        gzip_comp_level       4;
        gzip_types text/plain text/css application/json application/javascript application/x-javascript text/xml application/xml application/xml+rss text/javascript;

        # Include the Elastic Beanstalk generated locations
        include conf.d/elasticbeanstalk/*.conf;

        # Permanently redirecting to https
        return 301 https://$host$request_uri;
    }
}
```

#### Verify config files

You should now verify that you have created each of the files above, here are the files you should have created:

```sh
.ebextensions/options.config
.ebextensions/sec-group.config
.ebextensions/ssl-files.config
.platform/nginx/conf.d/https.conf
.platform/nginx/nginx.conf
```

### Create the Beanstalk environment (this deploys as well)

The next steps depend on the steps above, to include `eb init`. We'll be using the [eb create command](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb3-create.html). This command will deploy a single instance, without a load balancer, and we will use spot instances with the specified instance types:
```sh
eb create --single --enable-spot --instance-types t3.nano,t3.micro myEnvOnEb 
```

Once the deployment is finished you can go to the Elastic Beanstalk dashboard and click on the "Go to environment" link, or click on the Domain, which will look something like this:

**myEnvOnEb.eba-sadf23ds.us-west-2.elasticbeanstalk.com**

When viewing in your browser, it should not matter if you use `http://` or `https://` for the url, you should be redirected to the https page. As we are using a self-signed certificate, you will see a warning that looks like this:

![Cert warning](https://raw.githubusercontent.com/veloduff/deploy-secure-nodejs-env/main/_images/eb_launch_cert_warning.png)

Click on "Advanced" and then click on the message that says something similar to this "Proceed to myEnvOnEb.eba-srwf23ds.us-west-2.elasticbeanstalk.com (unsafe)".

You should see your app running on https, and you can check the certificate by clicking on the "Not Secure" button next to the URL.

![Final result](https://raw.githubusercontent.com/veloduff/deploy-secure-nodejs-env/main/_images/eb_final_result.png)

#### Check that the session is Secure and using HttpOnly

Use Chrome to load the page, and go to "View" -> "Developer" -> "Developer Tools". And then click on the "Application" tab, and in the "Storage" section, you should see "Cookies" and under that you should see the cookie that was set by the Node.js application. Both "HttpOnly" and "Secure" should be checked:

![View cookie](https://raw.githubusercontent.com/veloduff/deploy-secure-nodejs-env/main/_images/cookie_status.png)

### Remove and reset

You can go to the AWS Console to see which environments are running and remove them there. Or to remove an application environment (and instances) with the CLI, use `eb list` to show your environments, and `eb terminate` to remove them:

`[~/repos/app-testing]$ eb terminate <env_name>`

If you need to reset your environment, you can remove all the files and directories that were created by the setup command:

`rm -ri .ebignore .gitignore .platform .ebextensions .env` + certificate directory

## Conclusion

We're done! We have setup a secure, inexpensive Node.js development environment on AWS Elastic Beanstalk. This environment (if running 24/7), would cost about $6/month (using today's EC2 Spot prices). You now have the option of scaling to a production environment that would include a Load Balancer and official (not self-signed) SSL certificates. The setup for using SSL and redirecting to https is much easier when using a Load Balancer, as that is one of the functions that a Load Balancer was designed to do (but will cost more).

For just general tips for launching a Node.js application on Beanstalk, but not specific to https, have a look at: [Node.js app on Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create_deploy_nodejs_express.html)

## Additional configuration

To add **Managed updates** and to enable access to static files in the `/public` directory, add this to `.ebextensions/options.config`: 

```yaml
option_settings:
  aws:elasticbeanstalk:managedactions:
    ManagedActionsEnabled: true
    PreferredStartTime: "Mon:10:00"
  aws:elasticbeanstalk:managedactions:platformupdate:
    UpdateLevel: patch
    InstanceRefreshEnabled: true
  aws:elasticbeanstalk:environment:proxy:staticfiles:
    /public: /public
```

