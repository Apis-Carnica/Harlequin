#!/usr/bin/python3

import os
import random
from datetime import datetime, timedelta
import discord
from dotenv import load_dotenv
import smtplib
import ssl
import mysql.connector
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# These will be placed inside the main function in discord to create variables
# on an as-needed basis

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
WELCOME = os.getenv('WELCOME_MESSAGE')
GUILD_ID = os.getenv('GUILD_ID')
ROLE = os.getenv('ROLE_NAME')
EMOJI = os.getenv('EMOJI')
SRC_EMAIL = os.getenv('BOT_EMAIL')
EMAIL_PASS = os.getenv('EMAIL_PASSWD')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASSWD')

def connect():
    return mysql.connector.connect(
        host='localhost',
        user=DB_USER,
        password=DB_PASS,
        database="harlequin")

def set_record(dst_email, username, code, expiry):
    """
    Takes the variables and sets them as a record in the auth table if the
    email isn't in the verified table
    """
    conx = connect()
    cursor = conx.cursor()
    sql = "INSERT INTO auth (email, username, code, expiry) VALUES (%s, %s, %s, %s)"
    val = (dst_email, username, code, expiry)
    cursor.execute(sql, val)
    conx.commit()

def check_record(code, username):
    """
    Sends a SELECT query from the auth server and verifies the variables.
    Returns True if the code supplied matches the one populating the record.
    """
    conx = connect()
    cursor = conx.cursor()
    sql = "SELECT * FROM auth WHERE username = %s"
    val = (username, )
    cursor.execute(sql, val)
    result = cursor.fetchall()
    print(result[0][2] + ' - ' + code + '->' + str(bool(str(result[0][2]) == code)))
    return bool(str(result[0][2]) == code)

def delete_record(field):
    "Deletes the selected table from the table"
    # Check for symbols to qualify index type: username -> email
    conx = connect()
    cursor = conx.cursor()
    sql = ""
    val = (field, )
    if field[-5] == '#':
        sql = "DELETE FROM auth WHERE username = %s"
    else:
        sql = "DELETE FROM auth WHERE email = %s"
    cursor.execute(sql, val)
    conx.commit()


def set_verified(username):
    "Moves the verified username and email to the verified table"
    conx = connect()
    cursor = conx.cursor()
    sql = "SELECT * FROM auth WHERE username = %s"
    val = (username, )
    cursor.execute(sql, val)
    email = cursor.fetchall()[0][0]
    sql = "INSERT INTO verified (email, username) VALUES (%s, %s)"
    val = (email, username)
    cursor.execute(sql, val)
    conx.commit()

def check_verified(dst_email):
    """
    Checks that the email isn't already verified before starting verification.
    Returns True if the email isn't found in the verified database
    """
    conx = connect()
    cursor = conx.cursor()
    sql = "SELECT * FROM verified WHERE email = %s"
    var = (dst_email, )
    cursor.execute(sql, var)
    result = cursor.fetchall()
    return bool(len(result) == 0)

def send_email(code, dst_email):
    "Sends an email to the student seeking verification"
    email_text = """Greetings!
    This email was sent to verify your discord account. To ensure that this
    email address belongs to you, please reply to the bot with '!verify'
    followed by your code: {}.
    If you run into issues, feel free to contact the @administrator & @moderator
    roles, post in the #tech-support channel, or message Ursa#1337 with any
    questions.
    """.format(code)

    email_html = """
    <html>
        <body>
            <p><b>Greetings!</b><br>
            This email was sent to verify your discord account. To ensure that this email address belongs to you, please reply to the bot with '!verify' followed by your code: {}.</p>
            <p>If you run into issues, feel free to contact the @administrator & @moderator roles, post in the #tech-support channel, or message Ursa#1337 with any questions.</p>
        </body>
    </html>
    """.format(code)

    p1 = MIMEText(email_text, "plain")
    p2 = MIMEText(email_html, "html")

    message = MIMEMultipart("alternative")
    message["Subject"] = "Verification Code"
    message["From"] = SRC_EMAIL
    message["To"] = dst_email
    message.attach(p1)
    message.attach(p2)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SRC_EMAIL, EMAIL_PASS)
        server.sendmail(
            SRC_EMAIL, dst_email, message.as_string()
        )

client = discord.Client()

@client.event
async def on_ready():
    print("Logged on as {}".format(client.user))


@client.event
async def on_raw_reaction_add(payload):
    dm = """**Greetings!**
    Let's get you verified!

    Reply with '`!email`', followed by your *student* email address.
    (Ex. !email jsmith01@wgu.edu)

    An email will be sent to you with a verification code and further instructions. If you're not able to find the email, try waiting a few minutes, refresh your mailbox, or check your spam folder.
    """
    if str(payload.message_id) == WELCOME:
        global guild_id
        guild_id = payload.guild_id
        if payload.emoji.name == EMOJI:
            await client.get_user(payload.user_id).send(dm)


@client.event
async def on_message(message):
    if message.channel.recipient == message.author:
        if message.content.startswith('!email'):
            dst_email = message.content.split(' ')[-1]
            code = []
            for _ in range(6):
                code.append(str(random.randint(0,9)))
            code = ''.join(code)
            expiry = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            username = str(message.channel.recipient)

            if bool(check_verified(dst_email)):
                set_record(dst_email, username, code, expiry)
                send_email(code, dst_email)
                await message.channel.send("An email was sent to the address you provided. If you have trouble finding it, try refreshing your browser, wait a few minutes or check your spam folder. Feel free to reach out to **Ursa#1337** with any questions you have.")

            else:
                await message.channel.send("That email has already been verified. If you think message in error, please make a post in tech-support so our moderators can assist you.")

        elif message.content.startswith('!verify'):
            code = message.content.split(' ')[-1]
            username = str(message.channel.recipient)

            if bool(check_record(code, username)):
                set_verified(username)
                delete_record(username)

                guild = client.get_guild(int(GUILD_ID))
                print(guild.id)
                role = discord.utils.get(guild.roles, name='valid')
                print(role.name)
                member = discord.utils.find(lambda m : m.id == message.channel.recipient.id, guild.members)
                print(member.id)
                if role is not None:
                    if member is not None:
                        await member.add_roles(role)
                        await message.channel.send("You're all set! We look forward to learning with you!")
                    else:
                        print("Member doesn't exist.")
                else:
                    print("Role doesn't exist or is misconfigured in '.env'.")
            else:
                await message.channel.send("It looks like your code is wrong, please try again.")

        elif message.content.startswith('!delete'):
            field = message.content.split(' ')[-1]

            delete_record(field)
            message.channel.send("We'll get that taken care of for you!")

        else:
            pass


client.run(TOKEN)
