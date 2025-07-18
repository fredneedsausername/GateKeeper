# Problem

The client is an italian shipyard company with 4000 workers in its high season, and 350 in its low season. The need is to keep logs of the permanence details for every crew member in their shipyards. The spoken language is italian.

# Solution

## Timezone

There is no timezone management in the whole application. It is assumed that every shipyard is in the same timezone.

## About ORMs

This project is against ORMs, and the raw connector will be used to perform all the operations on the database. A connection pool is used for better performance.

## Stack

It's important to choose the right stack for the job. This robust combination ensures a smooth user experience without sacrificing development speed.

### Frontend
- **Structure:** Multi Page Application
- **Reactivity:** Alpine.js + HTMX
- **Styling:** CSS

### Backend
- **Language:** Python
- **Framework:** Flask
- **Auth:** Cookies

### Database
- **DBMS:** PostgreSQL
- **Connector:** psycopg3

### Production
- **Server:** Waitress

## DB Schema

CREATE DATABASE GateKeeper WITH ENCODING 'UTF8';

-- "users" is plural to avoid conflict with keyword USER
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS shipyard (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS activator_beacon (
    id SERIAL PRIMARY KEY,
    mac_address MACADDR UNIQUE,
    shipyard_id INTEGER,
    is_first_when_entering BOOLEAN,
    CONSTRAINT fk_beacon_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES shipyard(id) 
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tag (
    id SERIAL PRIMARY KEY,
    name VARCHAR(29) UNIQUE,
    remaining_battery REAL,
    packet_counter INTEGER
);

CREATE TABLE IF NOT EXISTS crew_member_roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS ship (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS crew_member (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    role_id INTEGER,
    ship_id INTEGER,
    tag_id INTEGER,
    CONSTRAINT fk_crew_role 
        FOREIGN KEY (role_id) 
        REFERENCES crew_member_roles(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_crew_ship 
        FOREIGN KEY (ship_id) 
        REFERENCES ship(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_crew_tag 
        FOREIGN KEY (tag_id) 
        REFERENCES tag(id) 
        ON DELETE SET NULL,
    CONSTRAINT unique_tag_assignment UNIQUE (tag_id)
);

CREATE TABLE IF NOT EXISTS permanence_log (
    id SERIAL PRIMARY KEY,
    crew_member_id INTEGER,
    _id INTEGER,
    entry_timestamp TIMESTAMP,
    leave_timestamp TIMESTAMP,
    CONSTRAINT fk_log_crew 
        FOREIGN KEY (crew_member_id) 
        REFERENCES crew_member(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_log_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES shipyard(id) 
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unassigned_tag_entry (
    id SERIAL PRIMARY KEY,
    tag_id INTEGER,
    shipyard_id INTEGER,
    advertisement_timestamp TIMESTAMP,
    is_entering BOOLEAN,
    CONSTRAINT fk_entry_tag 
        FOREIGN KEY (tag_id) 
        REFERENCES tag(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_entry_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES shipyard(id) 
        ON DELETE CASCADE
);

CREATE USER your_user WITH PASSWORD 'your_strong_password';

GRANT CONNECT ON DATABASE your_database_name TO your_user;

GRANT USAGE ON SCHEMA public TO your_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO your_user;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO your_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO your_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO your_user;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE USAGE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE your_database_name FROM PUBLIC;

## Physical systems

The solution deploys a tag system. Tags, upon entering an activator beacon's radius, publish an advertisement to a gateway that physically opens the gates of the shipyard. The advertisement is also relayed to an api endpoint of the application.

The advertisement is comprised of 5 parts:
 - the tag's name (structured like "BE_A1900299");
 - the tag's remaining battery;
 - the activator's id;
 - the previous activator's id;
 - the tag's packet counter.

## Leaving or entering?

### Idea

It is necessary determine whether the crew member is leaving or entering. Toggling the state at every tag advertisement can become dangerous. If one event is missed, the records become out of phase. To solve this, we put two activator beacons in sequence, and analyze the tag's advertisement to extract the order of activation.

### Implementation

#### Activator beacons

The ActivatorBeacon table contains all the information necessary to determine if an advertisement is valid, and if it is, then it has information to determine whether it signals entering or exiting.

If the past beacon to be triggered has is_first_when_entering set to true, and the current beacon has got it set to false, and they're from the same shipyard, then the person is entering.

If the past beacon to be triggered has is_first_when_entering set to false, and the current beacon has got it set to true, and they're from the same shipyard, then the person is exiting.

If the past beacon is from another shipyard than the current one, then the advertisement is to be ignored. Since, for the advertisement to be processed, a requirement is for the two activator beacons to be from the same shipyard, then this is the way that the shipyard of a processed advertisement is deduced, by taking either ActivatorBeacons' shipyard_id.

If the past beacon is the same as the current one, then the advertisement is to be ignored.

If either the past or the current beacon don't exist in the table, then the advertisement is to be ignored.

If the adverisement has past activator id equal to 0 then the advertisement is to be ignored, because 0 is the fallback value when there is no past beacon, and the implementation forces to have no beacon with id equal to zero.

#### Tags

If the tag name of the advertisement is not found in the table then a new Tag row is created in the db, taking the information from the advertisement, and continue processing the advertisement.

Every single advertisement from a tag updates its battery level, even if the advertisement is not valid.

If the tag of the advertisement hasn't their packet counter already set in the table, then it is set to the one of the advertisement.

If the packet counter of the advertisement is the same as the value of the tag record, then the advertisement is to be ignored.

If the packet counter of the tag record is not the same as the value of the advertisement, then set it equal to the one of the advertisement, and continue processing the advertisement.

## Logs

If a person enters, then exits, a log is first created, then it is closed.

If a person enters, then gets assigned to a new tag, then exits with that new tag, the same log is closed. These logs don't monitor the tags, but the people bearing them, and are blind to the history of the tag assignments.

If a person enters, then their exit is not registered by system, and they enter again, two open logs are created. If then this person exits, the more recently created record gets closed, and the older record will never be closed by the system, even if that person were to exit two times in a row.

If a person exits but all their past logs are closed, a new log that only registers them exiting is created. This record will never be opened by the system, even if that person enters later, but it can be opened manually by an operator.

So, this demonstates that a log with only the exit timestamp and without the entry timestamp can exist.

In general, only the most recent log is updated by the system and, after a log is closed, even if it never started, whether there is an entry or an exit following after, a new one is always created.

More info about the logs is found in the "# View" section.

A tag always opens the gates, and is independent of the system's assignment to people. It follows that an edge case is unregistered tags.

## Entries

Logs are kept for people, and entries for unassigned tags.

Logs can be opened and can be closed, but tag entries can only be created.

Entries represent either an entry or a leave event.

More info about entries is found in the "# View" section.

## Handling edge cases

Edge cases are best handled if manually and by the user. They are free to create new logs, and to modify existing ones to add new enter or leave events. There is no point in creating entries, because they are non identifiable and thus not interesting to the user. They only serve the purpose of knowing if someone unauthorized entered the shipyards, and which tags left the shipyard.

# View

## Base template

The base template features a sidebar to the left, and a section at the top where the user can check their profile and the name of the ERP.

## Login 

The login page lets the users log in with their username and password.

The password is kept as plaintext in the database for conveniece.

## Register

There is no such page! All of the users are manually registered by the sysadmin, that logs into the database console and creates new rows for the User table.

## Crew members

### Manage crew members

The user can apply filters to what is shown on the table. All filters will be applied and the records that match all filters will be shown. All the results are shown in ascending order of the crew members' names. Each filter can be reset, and if a filter is not set then it will not impact the results shown.

The user can fiter by a specific ship, using case insensitive substring search with the trimmed query string to dynamically update the alphabetically ordered droplist to select from, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can fiter by crew member name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can fiter by a specific role, using case insensitive substring search with the trimmed query string to dynamically update the alphabetically ordered droplist to select from, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The default filter, if none is specified, is to not actually have a filter, but to use a different approach instead. No crew member is shown until the user filters by something, because they want to filter the results according to their needs.

The filtered info is shown in a table, that is structured like this:

|Tag        |🔋%|Nave    |Equipaggio   |Ruolo   |Azioni   |
|-----------|---|--------|-------------|--------|---------|
|BE_A1900299| 85|Rossina |Roberto Verdi|Capitano|(buttons)|
|           |   |Bellezza|Mario Neri   |Crew    |(buttons)|

If no tag is currently assigned to a crew member, then the battery level and tag name for that row will be empty.

In place of "(buttons)" there are two buttons, one to go to the page to modify the crew member and one to delete them. Before deleting, a modal appears and asks for confirmation.

The first 50 results are loaded, and if the user needs more, when they scroll at the bottom 50 more results will be automatically loaded, and so on.

On top of the table, on the right there is a button to add a new crew member. The page where the button brings is described in a subsection.

### Modify crew member

This is a vertically developed single colum centered form to modify the crew member. The fields are displayed vertically, and the user can modify them.

The user can change the ship by searching for it by its name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the role by searching for it by its name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the name of the crew member because it is in a textbox.

The user can filter by and select a specific tag name, using the trimmed query string to dynamically update the alphabetically ordered droplist to select from, matching it with the exact tag name, after 500 milliseconds have passed since the last interaction of the user with the textbox.

At the bottom there are two buttons: one for applying the changes and the other to cancel the operation.

### Create crew member

This is a vertically developed single colum centered form to create the crew member. The fields are displayed vertically, and the user can insert and modify them.

The user can change the ship by searching for it by its name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the role by searching for it by its name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the name of the crew member because it is in a textbox.

The user can filter by and select a specific tag name, using the trimmed query string to dynamically update the alphabetically ordered droplist to select from, matching it with the exact tag name, after 500 milliseconds have passed since the last interaction of the user with the textbox.

At the bottom there are two buttons: one for creating the crew member and the other to cancel the operation.

## Ships

### Manage ships

The user can apply filters to what is shown on the table. All filters will be applied and the records that match all filters will be shown. All the results are shown in ascending order of the ships' names. Each filter can be reset, and if a filter is not set then it will not impact the results shown.

The user can fiter by ship name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The default filter, if none is specified, is to not actually have a filter, but to use a different approach instead. No ship is shown until the user filters by something, because they want to filter the results according to their needs.

The data is shown on a table:

|Nave    |Azioni   |
|--------|---------|
|Rossina |(buttons)|
|Bellezza|(buttons)|

In place of "(buttons)" there are two buttons, one to go to the page to modify the ship and one to delete it. Before deleting, a modal appears and asks for confirmation.

The first 50 results are loaded, and if the user needs more, when they scroll at the bottom 50 more results will be automatically loaded, and so on.

On top of the table, on the right there is a button to add a new ship. The page where the button brings is described in a subsection.

### Modify ship

This is a vertically developed single colum centered form to modify the ship. The fields are displayed vertically, and the user can modify them.

The user can change the name of the ship because it is in a textbox.

At the bottom there are two buttons: one for applying the changes and the other to cancel the operation.

### Create ship

This is a vertically developed single colum centered form to create the ship. The fields are displayed vertically, and the user can insert or modify them.

The user can change the name of the ship because it is in a textbox.

At the bottom there are two buttons: one to create the ship and the other to cancel the operation.

## Tags

### Manage Tags

This is a menu to manage all the tags, where the user finds two checkboxes to filter through them. These two checkboxes are, by default, unticked. The user can tick one or both checkboxes at the same time, to select what they see. The displayed results appear in order of lowest to highest battery. The two checkboxes have the following labels: "Assegnati"; "Vacanti". The "Assegnati" checkboxes shows the tags that are assigned to a crew member, and the "Vacanti" checkbox shows the tags that are not assigned to any crew member.

When tags are selected this way, the shown fields are:
- the tag's name;
- the tag's remaining battery;
- the crew member's name.

In a table like this:

|Tag        |🔋%|Equipaggio   |Azioni   |
|-----------|---|-------------|---------|
|BE_A1900299|  9|Mario Neri   |(buttons)|
|BE_A8227461| 85|             |(buttons)|

Where one of the buttons is for deleting the tag, and the other one is to modify it.

### Modify tag

This is a vertically developed single colum centered form to modify the tag. The fields are displayed vertically, and the user can modify them.

The user can reassign the tag by searching for the crew member name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the name of the tag because it is in a textbox.

At the bottom there are two buttons: one for applying the changes and the other to cancel the operation.

### Create tag

This is a vertically developed single colum centered form to create the tag. The fields are displayed vertically, and the user can insert and modify them.

The user can assign the tag by searching for the crew member name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the name of the tag because it is in a textbox.

At the bottom there are two buttons: one for creating the tag and the other to cancel the operation.

## Entries

### Filters

The user can apply filters to what is shown on the table. All filters will be applied and the records that match all filters will be shown. All the results are shown in ascending order of tags' remaining battery. Each filter can be reset, and if a filter is not set then it will not impact the results shown.

The user can filter by start timestamp and by end timestamp, and only UnassignedTagEntry records with an advertisement_timestamp that falls within the interval of time that is between the start timestamp of the filter and the end timestamp of the filter are going to be shown on the table.

The user can filter by a specific shipyard, using case insensitive substring search with the trimmed query string to dynamically update the alphabetically ordered droplist to select from, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can filter by a specific tag name, using the trimmed query string to dynamically update the alphabetically ordered droplist to select from, matching it with the exact tag name, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The default filter, if none is specified, is for a start timestamp of 24 hours before the current time, and an end timestamp that is of when the page is requested.

### Manage entries

The filtered info is shown in a table, that is structured like this:

|Cantiere|Tag        |🔋%|Passaggio          |Tipologia|Azioni  |
|--------|-----------|---|-------------------|---------|--------|
|Ponente |BE_A1900299| 85|06/05/2025 18:42:11|Ingresso |(button)|
|Ponente |BE_A8227461|  9|07/05/2025 09:54:47|Uscita   |(button)|

In this table:
- cantiere is the shipyard of the entry;
- passaggio is the advertisement_timestamp;
- tag is the name of the unregistered tag;
- the battery emoji is the current battery level of the tag.

The button is to delete the row. Before deleting, a modal appears and asks for confirmation.

The first 50 results are loaded, and if the user needs more, when they scroll at the bottom 50 more results will be automatically loaded, and so on.

There is no way to modify or create entries.

## Logs

### Filters

The user can apply filters to what is shown on the table. All filters will be applied and the records that match all filters will be shown. All the results are shown in ascending order of the crew members' names. Each filter can be reset, and if a filter is not set then it will not impact the results shown.

The user can filter by start timestamp and by end timestamp, and only PermanenceLog records that have any overlap with the interval of time that is between their own entry_timestamp and their own leave_timestamp and the interval of time that is between the start timestamp of the filter and the end timestamp of the filter are going to be shown on the table.

The user can filter by a specific shipyard, using case insensitive substring search with the trimmed query string to dynamically update the alphabetically ordered droplist to select from, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can fiter by a specific ship, using case insensitive substring search with the trimmed query string to dynamically update the alphabetically ordered droplist to select from, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can fiter by crew member name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The default filter, if none is specified, is for a start timestamp of 24 hours before the current time, and an end timestamp that is of when the page is requested.

### Manage logs

The filtered info is shown in a table, that is structured like this:

|Cantiere|Tag        |🔋%|Nave    |Equipaggio   |Ruolo   |Entrata            |Uscita             |Azioni   |
|--------|-----------|---|--------|-------------|--------|-------------------|-------------------|---------|
|Ponente |BE_A1900299| 85|Rossina |Roberto Verdi|Capitano|06/05/2025 18:42:11|                   |(buttons)|
|Ponente |           |   |Bellezza|Mario Neri   |Crew    |07/05/2025 09:54:47|08/05/2025 13:12:16|(buttons)|

In this table:
- cantiere is the shipyard of the permanence log;
- nave is info of the crew member;
- ruolo is info of the crew member;
- entrata and uscita are the entry and leave timestamps;
- tag is the name of the tag that the crew member is currently bearing;
- the battery emoji is the current battery level of the tag that the crew member is currently bearing.

The shown tag is the one that the crew member is bearing in this exact moment. It has nothing to do with the tag that was used in the events that made the permanence log. In the table it appears as empty in one row because, in this example, it was unassigned after the crew member left the shipyard.

In this example, in one row, the exit event is missing because the crew member is still inside of the shipyard.

One of the buttons is for modifying the row, the other one to delete it. Before deleting, a modal appears and asks for confirmation.

The first 50 results are loaded, and if the user needs more, when they scroll at the bottom 50 more results will be automatically loaded, and so on.

On top of the table, on the right there is a button to add a new log. The page where the button brings is described in a subsection.

### Modify log

This is a vertically developed single colum centered form to modify the log. The Equipaggio, Entrata, Uscita fields are displayed vertically, and the user can modify them.

The user can change the crew member by searching for them by their name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the Entrata and Uscita with a datetime selector that can be reset. At least one of them has to not be null, and this is enforced client and server side.

At the bottom there are two buttons: one for applying the changes and the other to cancel the operation.

### Create log

This is a vertically developed single colum centered form to create the log. The fields are displayed vertically, and the user can insert and modify them.

The user can change the crew member by searching for them by their name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the shipyard by searching for them by their name, using case insensitive substring search with the trimmed query string to dynamically update the table with all the entries that match, showing the data in alphabetical order, after 500 milliseconds have passed since the last interaction of the user with the textbox.

The user can change the Entrata and Uscita with a datetime selector that can be reset.

At the bottom there are two buttons: one for creating the log and the other to cancel the operation.