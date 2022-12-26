# p

Password database

2022 written by Jens Heine <binbash@gmx.net>

If. you are paranoid when it comes to passwords and privacy you may want
to have a password safe for your accounts. Then you do not trust all the
password safes that exist and you write the password safe by yourself.

This is what I do here. The code is short, simple and I did NOT invent
a new proprietary encryption function. I use open source cryptography
which has been tested and which is hopefully bugfree :)

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

HOW DO I START?

You can start with creating a new account (the initial master database password will be requested):

>./p -a

To search an account the includes the word "gmx" use the -s option:

>./p -s gmx

or the fast way:

>./p gmx

Maybe you want to change the master database password, then do this:

>./p -c

You can even set an empty password which will make the database unencrypted. This is usefull if you want to make bulk changes with an sqlite browser of your choice. p uses a sqlite db which can be opened and edited with any sqlite browser. After you have edited the database with the sqlite browser, you can ecrypt the database again with a password.

You will be asked for the old and the new password and the the entire database content will be re encrypted with the new password.

Howto syncronize multiple versions/databases?

If you have a version on an usb stick and one on a laptop and so on, you can sync them this way:

>./p -M /path/to/other/database

This will update both databases to the same state.

WHAT FEATURES CAN I USE?

Use the -h option to show all options:

>./p -h

You can also move the binary to a folder in your path and set an environment variable LASTBASE_DATABASE=<path_to_database_file>. Then you can call "p <search_string>" from everywhere in your console.

keep coding,
Jens
