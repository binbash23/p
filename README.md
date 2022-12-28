# p

Password database

2022 written by Jens Heine <binbash@gmx.net>

If you are paranoid when it comes to passwords and privacy you may want
to have a password safe for your accounts. Then you do not trust all the
password safes that exist and you write the password safe by yourself.

This is what I do here. The code is short, simple and I did NOT invent
a new proprietary encryption function. I use open source cryptography
which has been tested and which is hopefully bugfree :)
For the people who want to know, I use this for the symetric encryption method:
> _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=500000)

> key = base64.urlsafe_b64encode(_hash.derive(password))

and the salt is static but long and random (see source code)

Try it out. Gimme feedback. 

I take advantage of sqlite as a database, so you can store a huge
amount of accounts.

The program code can be understood by everyone who codes at least a 
little it.

Binaries/executeable program:
You can use the python code or the binaries that I have compiled to the folder 

"p/dist/linux/p"
or
"p/dist/windows/p.exe"

I copy the linux and the windows binary to an usb stick and also my p.db file (which holds all the encrypted accounts). With this usb stick I have all my accounts reachable on any computer even without internet!

# HOW DO I START?

You might doubleklick on the windows binary (p.exe) and a cmd window will appear. Enter the password for your new password database and thats all.


Using Database: p.db

Database does not exist.

Enter password for new database    :

Confirm password for new database  :

Creating new p database: "p.db" ...

Creating new UUID for database: 6ed88bba-a210-4150-8e10-76f57b347770

Shell mode enabled. Use 'quit' or strg-c to quit or help for more infos.

DB: p.db> add

Add account

UUID      : 8d3a4c15-4780-459c-a3f5-ba1586c043df

Name      : New Account

URL       : www.new.de

Loginname : horst

Password  : meinpw

Type      : Webaccount

Correct ([y]/n) :

New account added.

Added

DB: p.db> list

Searching for ** in 1 accounts:

ID          : 8d3a4c15-4780-459c-a3f5-ba1586c043df

Name        : New Account

URL         : www.new.de

Loginname   : horst

Password    : meinpw

Type        : Webaccount


Found 1 result(s).

DB: p.db>



keep coding,
Jens
