import sqlite3
import datetime
from utils import date_string_to_date, get_mic_state

conn = sqlite3.connect('user_info.db')
c = conn.cursor()

# Todo: Die user_info und voice_channel_info sollten nochmal überarbeitet werden.
# Dokumentieren, was die einzelnen Felder bedeuten und welche Werte sie annehmen können. Bin jedes Mal selbst verwirrt.
c.execute('''CREATE TABLE IF NOT EXISTS user_info (
    user_id INTEGER,
    server_id INTEGER,
    username TEXT,
    status TEXT,
    unmuted_time REAL,
    last_join_time TEXT,
    total_time_muted REAL,
    total_time_sound_muted REAL,
    current_state TEXT,
    last_state_change_time TEXT,
    activity TEXT,
    avatar TEXT,
    roles TEXT,
    premium_since TEXT,
    joined_at TEXT,
    created_at TEXT,
    is_bot INTEGER,
    PRIMARY KEY (user_id, server_id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS voice_channel_info
             (user_id INTEGER,
              server_id INTEGER,
              voice_channel TEXT,
              total_time REAL,
              PRIMARY KEY (user_id, server_id)
             )''')

c.execute('''CREATE TABLE IF NOT EXISTS online_status_time (
            user_id INTEGER,
            server_id INTEGER,
            online_total REAL,
            offline_total REAL,
            idle_total REAL,
            dnd_total REAL,
            last_status_change TEXT,
            PRIMARY KEY (user_id, server_id),
            FOREIGN KEY (user_id, server_id) REFERENCES user_info (user_id, server_id)
            );''')

c.execute('''CREATE TABLE IF NOT EXISTS heartbeat (
            id INTEGER PRIMARY KEY,
            last_heartbeat TEXT
            );''')

c.execute('''CREATE TABLE IF NOT EXISTS downtime (
            id INTEGER PRIMARY KEY,
            "from" DATETIME,
            "to" DATETIME
             );''')


def update_heartbeat():
    """Function to update the heartbeat table"""

    query = '''INSERT INTO heartbeat (last_heartbeat) VALUES (?)'''
    args = (datetime.datetime.now(),)
    c.execute(query, args)
    conn.commit()


def user_exists(user_id, server_id):
    """Funktion zum Überprüfen, ob ein Benutzer in der Datenbank existiert"""

    query = '''SELECT EXISTS(SELECT 1 FROM user_info WHERE user_id = ? AND server_id = ?)'''
    result = c.execute(query, (user_id, server_id)).fetchone()[0]
    return result == 1


def insert_user(member):
    """Funktion zum Einfügen eines neuen Benutzers in die Datenbank"""

    query = '''
    INSERT INTO user_info (user_id, server_id, username, status, unmuted_time, last_join_time,
                           total_time_muted, total_time_sound_muted, current_state, last_state_change_time,
                           activity, avatar, roles, premium_since, joined_at, created_at, is_bot)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    c.execute(query, (member.id, member.guild.id, member.name, str(member.status), 0, datetime.datetime.utcnow(), 0, 0, '',
                      datetime.datetime.utcnow(), str(member.activity.name if member.activity else ''), str(member.avatar.url if member.avatar else member.default_avatar),
                      str(', '.join(role.name for role in member.roles)), str(member.premium_since),
                      str(member.joined_at), str(member.created_at), member.bot))

    conn.commit()


def update_user_data(member, before, after, update_join_time=True, update_state_change_time=True, initial_scan=False):
    """Hauptfunktion zum Aktualisieren der Benutzerdaten. Diese Funktion wird immer dann aufgerufen,
    wenn sich der Benutzer in einem Voice-Channel bewegt, den Server betritt oder verlässt or every SCAN_INTERVAL seconds.
    Wenn der User jedoch seinen Mute-Status ändert, wird direkt die Funktion update_mute_data() aufgerufen.
    Parameter:
        member - Member,
        before - VoiceState,
        after - VoiceState,
        update_join_time - bool,
        update_state_change_time - bool,"""

    # Since database changes are being made here, it is important that the calls are made in the correct order. This must not be changed.
    update_voice_channel_data(member, before, after, initial_scan=initial_scan)
    update_mute_data(member, before, after)
    update_online_status_time(user_id=member.id, status=str(member.status), initial_scan=initial_scan)

    query = '''
    UPDATE user_info
    SET status = ?,
        activity = ?,
        avatar = ?,
        roles = ?,
        premium_since = ?,
        joined_at = ?,
        created_at = ?,
        is_bot = ?
    '''
    if update_join_time:
        query += ', last_join_time = ?'
    if update_state_change_time:
        query += ', last_state_change_time = ?'
    query += ' WHERE user_id = ? AND server_id = ?'

    args = [str(member.status),
            str(member.activity.name if member.activity else ''),
            str(member.avatar.url if member.avatar else member.default_avatar),
            ', '.join(role.name for role in member.roles),
            str(member.premium_since),
            str(member.joined_at),
            str(member.created_at),
            member.bot]

    if update_join_time:
        args.append(datetime.datetime.utcnow())
    if update_state_change_time:
        args.append(datetime.datetime.utcnow())

    args.append(member.id)
    args.append(member.guild.id)
    c.execute(query, tuple(args))

    # Voice-Channel-Status aktualisieren
    query = '''
        UPDATE voice_channel_info
        SET voice_channel = ?
        WHERE user_id = ? AND server_id = ?
        '''
    args = [after.name if after else '',
            member.id, member.guild.id]
    c.execute(query, tuple(args))

    conn.commit()



def update_mute_data(member, before, after):
    if before is None and after is None:
        return

    current_state = get_mic_state(member)

    query = f'SELECT current_state, last_state_change_time FROM user_info WHERE user_id = ? AND server_id = ?'
    result = c.execute(query, (member.id, member.guild.id)).fetchone()

    previous_state, last_state_change_time_str = result

    last_state_change_time = None
    if last_state_change_time_str is not None:
        last_state_change_time = date_string_to_date(
            last_state_change_time_str)

    if previous_state == 'muted':
        field_name = 'total_time_muted'
    elif previous_state == 'sound-muted':
        field_name = 'total_time_sound_muted'
    else:
        field_name = 'unmuted_time'

    if last_state_change_time is not None:
        time_spent_in_previous_state = (
            datetime.datetime.utcnow() - last_state_change_time).total_seconds()
    else:
        time_spent_in_previous_state = 0

    time_spent_in_previous_state = round(time_spent_in_previous_state, 2)

    query = f'''
            UPDATE user_info
            SET last_state_change_time = ?,
            current_state = ?
            '''
    if before is not None:
        query += f', {field_name} = {field_name} + ?'

    query += ' WHERE user_id = ? AND server_id = ?'

    args = [datetime.datetime.utcnow(), current_state]
    if before is not None:
        args.append(time_spent_in_previous_state)
    args.append(member.id)
    args.append(member.guild.id)
    c.execute(query, tuple(args))

    conn.commit()


def update_online_status_time(before=None, after=None, user_id=1, status='', initial_scan=False) -> None:
    """
    Based on the last online status change, adds the time that the user spent in this status (Online, Offline, Idle, Do Not Disturb).
                 Because the online status is updated every X seconds by the main.py => scan_server()
                 and in this case there is no "before" and "after" VoiceState, the parameters "before" and "after" are None by default.
                 In this case, the user_id and status are then passed manually. If "before" and "after" are not None, user_id and status are ignored.
    Parameter: 
        before - VoiceState 
        after - VoiceState
        user_id - int
        status - str
    """
    if initial_scan:
        # Fix for issue #1: Update once so that the online status time can be calculated correctly again from this point onwards
        # if the bot was offline for a certain period of time.
        c.execute('''UPDATE online_status_time
                    SET last_status_change = ?
                    WHERE user_id = ?''', (datetime.datetime.utcnow(), user_id))
        conn.commit()
        return

    now = datetime.datetime.utcnow()

    if before is None and after is None:
        query = '''SELECT last_status_change FROM online_status_time WHERE user_id = ?'''
        last_status_change = c.execute(query, (user_id,)).fetchone()

        if last_status_change is None:
            # We need to substrac SCAN_SERVER_INTERVAL from the current time, because otherwise the time is wrong at the initial scan.
            last_status_change = now
        else:
            last_status_change = date_string_to_date(last_status_change)

        time_diff = (now - last_status_change).total_seconds()
        time_diff = round(time_diff, 2)

        c.execute(f'''UPDATE online_status_time
                    SET {get_status_column_name(status)} = IFNULL({get_status_column_name(status)}, 0) + ?,
                        last_status_change = ?
                    WHERE user_id = ?''', (time_diff, now, user_id))
        conn.commit()
        return

    c.execute('''UPDATE user_info
                     SET status = ?
                     WHERE user_id = ?''', (str(after.status), before.id))
    conn.commit()

    column_name = get_status_column_name(before.status)

    query = '''SELECT last_status_change FROM online_status_time WHERE user_id = ?'''
    last_status_change = c.execute(query, (before.id,)).fetchone()

    if last_status_change is None:
        last_status_change = now.strftime('%Y-%m-%d %H:%M:%S.%f')

    # Differnz zwischen dem letzten Status-Change und dem jetzigen Zeitpunkt berechnen
    time_diff = (now - date_string_to_date(last_status_change)).total_seconds()

    time_diff = round(time_diff, 2)

    c.execute(f'''UPDATE online_status_time
                  SET {column_name} = IFNULL({column_name}, 0) + ?,
                      last_status_change = ?
                  WHERE user_id = ?''', (time_diff, now, before.id))
    conn.commit()


def update_voice_channel_data(member, before, after, initial_scan=False):
    if before is None and after is None:
        return

    if initial_scan:
        # Fix for issue #1: Update once so that the online status time can be calculated correctly again from this point onwards
        # if the bot was offline for a certain period of time.
        c.execute('''UPDATE user_info
                    SET last_state_change_time = ?
                    WHERE user_id = ? AND server_id = ?''', (datetime.datetime.utcnow(), member.id, member.guild.id))
        conn.commit()
        return

    now = datetime.datetime.utcnow()

    query = '''SELECT last_state_change_time FROM user_info
    WHERE user_id = ? AND server_id = ?'''

    last_state_change_time_str = c.execute(
        query, (member.id, member.guild.id)).fetchone()

    if last_state_change_time_str is not None:
        last_state_change_time = date_string_to_date(
            last_state_change_time_str)
        time_spent_in_channel = (
            now - last_state_change_time).total_seconds()
    else:
        time_spent_in_channel = 0

    time_spent_in_channel = round(time_spent_in_channel, 2)

    query = '''SELECT COUNT(*) FROM voice_channel_info
    WHERE user_id = ? AND server_id = ?'''

    count = c.execute(query, (member.id, member.guild.id)).fetchone()

    if count == 0:
        query = '''INSERT INTO voice_channel_info
        (user_id, server_id, total_time)
        VALUES (?, ?, ?)'''

        args = (member.id, member.guild.id, time_spent_in_channel)
        c.execute(query, args)
    else:
        # Anders als beim inserten, muss hier drauf geachtet werden, dass die Zeit nicht addiert wird,
        # sobald der User den Server betritt, sondern erst, wenn er den Server wieder verlässt.
        if before is not None:
            query = '''UPDATE voice_channel_info
            SET total_time = total_time + ?
            WHERE user_id = ? AND server_id = ?'''

            args = (time_spent_in_channel, member.id, member.guild.id)
            c.execute(query, args)

    conn.commit()


def get_status_column_name(status: str):
    if str(status) == 'online':
        return 'online_total'
    if str(status) == 'offline':
        return 'offline_total'
    if str(status) == 'idle':
        return'idle_total'
    if str(status) == 'dnd':
        return 'dnd_total'
