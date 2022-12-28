# p

# The Password database

__2022 written by Jens Heine <binbash@gmx.net>__

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

The program code can be understood by everyone who codes at least a 
little it.

keep coding,
Jens

### Binaries/executeable program:
You can use the python code or the binaries that I have compiled to the folder 

"p/dist/linux/p"
or
"p/dist/windows/p.exe"

I copy the linux and the windows binary to an usb stick and also my p.db file (which holds all the encrypted accounts). With this usb stick I have all my accounts reachable on any computer even without internet!

### How do I start?

You might doubleklick on the windows binary (p.exe) and a cmd window will appear. Enter the password for your new password database and thats all.


>Using Database: p.db<br>
>Database does not exist.<br>
>Enter password for new database    :<br>
>Confirm password for new database  :<br>
>Creating new p database: "p.db" ...<br>
>Creating new UUID for database: 6ed88bba-a210-4150-8e10-76f57b347770<br>
>Shell mode enabled. Use 'quit' or strg-c to quit or help for more infos.<br>
>DB: p.db> add<br>
>Add account<br>
>UUID      : 8d3a4c15-4780-459c-a3f5-ba1586c043df<br>
>Name      : New Account<br>
>URL       : www.new.de<br>
>Loginname : horst<br>
>Password  : meinpw<br>
>Type      : Webaccount<br>
>Correct ([y]/n) :<br>
>New account added.<br>
>
>DB: p.db> list<br>
>Searching for ** in 1 accounts:<br>
>ID          : 8d3a4c15-4780-459c-a3f5-ba1586c043df<br>
>Name        : New Account<br>
>URL         : www.new.de<br>
>Loginname   : horst<br>
>Password    : meinpw<br>
>Type        : Webaccount<br>
><br>
>Found 1 result(s).<br>
>DB: p.db><br>

### Cloud integration

Who wants to have a master database copy in the cloud can also do this by using my dropbox feature. First you have to enable your dropbox for an API connection. Then you can alway upload/sync your database with the copy in your personal dropbox account.<br>The procedure to enable dropbox is f&%$%&ing stupid complicated. So I wrote a help text for this [here](https://github.com/binbash23/p/blob/master/docs/howto_dropbox_configuration.txt).

### Merging different password databases

Usually you have different copies of your p database. One on your desktop computer, another on the laptop... To synchronize them, there is a merge feature to do this for you.

### SQLite database

I use the sqlite database to store the accounts (after I encrypt them). This is nice because you can use any [sqlite browser](https://sqlitebrowser.org/dl/) to open the database and do whatever you want: use sql, import export stuff, do bulk changes...<br>
Just decrypt all accounts before opening the database with the sqlite browser by setting an empty password and you then have a cleartext password database to browse through.<br>
Just make shure to encrypt the account after this by changing the password again to a non empty string.

### Help

For help just type help in the pshell or start p.exe like "p.exe -h"
