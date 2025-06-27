# Problem

The client is an italian shipyard company with 4000 workers in its high season, and 350 in its low season. The need is to keep logs of the permanence details for every crew member in their shipyards. The spoken language is italian.

# Solution

## Stack

It's important to choose the right stack for the job. This robust and modern combination ensures a smooth user experience without sacrificing development speed.

### Frontend
- **Structure:** Single Page Application
- **Framework:** Svelte
- **Styling:** Tailwind

### Backend
- **Language:** Python
- **Framework:** FastAPI
- **Auth:** JWT

### Database
- **DBMS:** PostgreSQL
- **Connector:** psycopg3

### Production
- **Deploy**: docker for backend and frontend, database managed separately

## DB Schema

CREATE DATABASE GateKeeper WITH ENCODING 'UTF8';

-- "Users" is plural to avoid conflict with keyword USER
CREATE TABLE Users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(20)
);

CREATE TABLE Shipyard (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50)
);

CREATE TABLE ActivatorBeacon (
    id SERIAL PRIMARY KEY,
    number INTEGER UNIQUE CHECK (number != 0),
    shipyard_id INTEGER,
    is_first_when_entering BOOLEAN,
    CONSTRAINT fk_beacon_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES Shipyard(id) 
        ON DELETE CASCADE
);

CREATE TABLE Tag (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) UNIQUE,
    remaining_battery REAL,
    packet_counter INTEGER
);

CREATE TABLE CrewMemberRoles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50)
);

CREATE TABLE Ship (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE CrewMember (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    role_id INTEGER,
    ship_id INTEGER,
    tag_id INTEGER,
    CONSTRAINT fk_crew_role 
        FOREIGN KEY (role_id) 
        REFERENCES CrewMemberRoles(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_crew_ship 
        FOREIGN KEY (ship_id) 
        REFERENCES Ship(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_crew_tag 
        FOREIGN KEY (tag_id) 
        REFERENCES Tag(id) 
        ON DELETE SET NULL
);

CREATE TABLE PermanenceLog (
    id SERIAL PRIMARY KEY,
    crew_member_id INTEGER,
    shipyard_id INTEGER,
    entry_timestamp TIMESTAMP,
    leave_timestamp TIMESTAMP,
    CONSTRAINT fk_log_crew 
        FOREIGN KEY (crew_member_id) 
        REFERENCES CrewMember(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_log_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES Shipyard(id) 
        ON DELETE CASCADE
);

CREATE TABLE UnassignedTagEntry (
    id SERIAL PRIMARY KEY,
    tag_id INTEGER,
    shipyard_id INTEGER,
    advertisement_timestamp TIMESTAMP,
    is_entering BOOLEAN,
    CONSTRAINT fk_entry_tag 
        FOREIGN KEY (tag_id) 
        REFERENCES Tag(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_entry_shipyard 
        FOREIGN KEY (shipyard_id) 
        REFERENCES Shipyard(id) 
        ON DELETE CASCADE
);

## File structure

The project is a monorepo for ease of development.

GateKeeper/
    frontend/
        src/
            components/
                common/
                    BaseTemplate.svelte
                    NavigationBar.svelte
                    Modal.svelte
                    SearchDropdown.svelte
                    DateTimeSelector.svelte
                    LoadingSpinner.svelte
                    Pagination.svelte
                auth/
                    LoginForm.svelte
                crew/
                    CrewMemberTable.svelte
                    CrewMemberForm.svelte
                    CrewMemberFilters.svelte
                ships/
                    ShipTable.svelte
                    ShipForm.svelte
                    ShipFilters.svelte
                tags/
                    TagTable.svelte
                    TagForm.svelte
                    TagFilters.svelte
                entries/
                    EntryTable.svelte
                    EntryFilters.svelte
                logs/
                    LogTable.svelte
                    LogForm.svelte
                    LogFilters.svelte
            routes/
                Login.svelte
                Dashboard.svelte
                crew/
                    ManageCrewMembers.svelte
                    CreateCrewMember.svelte
                    EditCrewMember.svelte
                ships/
                    ManageShips.svelte
                    CreateShip.svelte
                    EditShip.svelte
                tags/
                    ManageTags.svelte
                    CreateTag.svelte
                    EditTag.svelte
                entries/
                    ManageEntries.svelte
                logs/
                    ManageLogs.svelte
                    CreateLog.svelte
                    EditLog.svelte
            lib/
                api.js
                auth.js
                constants.js
                utils.js
                stores.js
            App.svelte
            main.js
        public/
            index.html
            favicon.ico
        package.json
        vite.config.js
        tailwind.config.js
        postcss.config.js

    backend/
        app/
            api/
                endpoints/
                    auth.py
                    crew_members.py
                    ships.py
                    tags.py
                    entries.py
                    logs.py
                    advertisements.py
                dependencies.py
                api.py
            core/
                config.py
                security.py
                dependencies.py
            crud/
                base.py
                crew_member.py
                ship.py
                tag.py
                entry.py
                log.py
                user.py
            db/
                base.py
                session.py
                init_db.py
            models/
                __init__.py
                user.py
                shipyard.py
                activator_beacon.py
                tag.py
                crew_member.py
                ship.py
                permanence_log.py
                unassigned_tag_entry.py
            schemas/
                __init__.py
                auth.py
                crew_member.py
                ship.py
                tag.py
                entry.py
                log.py
                advertisement.py
            services/
                advertisement_processor.py
                log_manager.py
                tag_assignment.py
            __init__.py
            main.py
        requirements.txt
        .env.example
        .env

    docs/
        api/
            openapi.json

    scripts/
        start-dev.sh
        start-prod.sh
        init-db.sh

    .gitignore
    LICENSE
    DESIGN-DOCUMENT.md
    README.md

## API

### Base URL
```
https://api.gatekeeper.example.com/api
```

### Authentication
All endpoints except `/auth/login` require JWT Bearer token authentication.

```
Authorization: Bearer <token>
```

### Common Response Schemas

#### Error Response
```json
{
  "detail": "string",
  "status_code": "integer"
}
```

#### Pagination Response
```json
{
  "items": [],
  "total": "integer",
  "page": "integer",
  "size": "integer",
  "pages": "integer"
}
```

---

### Authentication Endpoints

#### POST /auth/login
Login with username and password.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response 200:**
```json
{
  "access_token": "string",
}
```

#### GET /auth/me
Get current user information.

**Response 200:**
```json
{
  "id": "integer",
  "username": "string"
}
```

---

### Crew Members Endpoints

#### GET /crew-members
Get filtered list of crew members.

**Query Parameters:**
- `ship_name` (string, optional): Filter by ship name (case-insensitive substring)
- `crew_member_name` (string, optional): Filter by crew member name (case-insensitive substring)
- `role_name` (string, optional): Filter by role name (case-insensitive substring)
- `skip` (integer, default: 0): Number of records to skip
- `limit` (integer, default: 50, max: 100 (for droplists)): Number of records to return

**Response 200:**
```json
{
  "items": [
    {
      "id": "integer",
      "name": "string",
      "role": {
        "id": "integer",
        "role_name": "string"
      },
      "ship": {
        "id": "integer",
        "name": "string"
      },
      "tag": {
        "id": "integer",
        "name": "string",
        "remaining_battery": "float"
      }
    }
  ],
  "total": "integer"
}
```

#### GET /crew-members/{id}
Get a specific crew member.

**Response 200:**
```json
{
  "id": "integer",
  "name": "string",
  "role_id": "integer",
  "ship_id": "integer",
  "tag_id": "integer",
  "role": {
    "id": "integer",
    "role_name": "string"
  },
  "ship": {
    "id": "integer",
    "name": "string"
  },
  "tag": {
    "id": "integer",
    "name": "string",
    "remaining_battery": "float",
    "packet_counter": "integer"
  }
}
```

#### POST /crew-members
Create a new crew member.

**Request Body:**
```json
{
  "name": "string",
  "role_id": "integer",
  "ship_id": "integer",
  "tag_id": "integer" // optional
}
```

**Response 201:**
Same as GET /crew-members/{id}

#### PUT /crew-members/{id}
Update a crew member.

**Request Body:**
```json
{
  "name": "string",
  "role_id": "integer",
  "ship_id": "integer",
  "tag_id": "integer" // optional, null to unassign
}
```

**Response 200:**
Same as GET /crew-members/{id}

#### DELETE /crew-members/{id}
Delete a crew member.

**Response 204:**
No content

---

### Ships Endpoints

#### GET /ships
Get filtered list of ships.

**Query Parameters:**
- `name` (string, optional): Filter by ship name (case-insensitive substring)
- `skip` (integer, default: 0): Number of records to skip
- `limit` (integer, default: 50, max: 100 (for droplists)): Number of records to return

**Response 200:**
```json
{
  "items": [
    {
      "id": "integer",
      "name": "string"
    }
  ],
  "total": "integer"
}
```

#### GET /ships/{id}
Get a specific ship.

**Response 200:**
```json
{
  "id": "integer",
  "name": "string"
}
```

#### POST /ships
Create a new ship.

**Request Body:**
```json
{
  "name": "string"
}
```

**Response 201:**
Same as GET /ships/{id}

#### PUT /ships/{id}
Update a ship.

**Request Body:**
```json
{
  "name": "string"
}
```

**Response 200:**
Same as GET /ships/{id}

#### DELETE /ships/{id}
Delete a ship.

**Response 204:**
No content

---

### Tags Endpoints

#### GET /tags
Get filtered list of tags.

**Query Parameters:**
- `assigned` (boolean, optional): Filter by assigned status
- `vacant` (boolean, optional): Filter by vacant status
- `skip` (integer, default: 0): Number of records to skip
- `limit` (integer, default: 50, max: 100 (for droplists)): Number of records to return

**Response 200:**
```json
{
  "items": [
    {
      "id": "integer",
      "name": "string",
      "remaining_battery": "float",
      "packet_counter": "integer",
      "crew_member": {
        "id": "integer",
        "name": "string"
      } // null if unassigned
    }
  ],
  "total": "integer"
}
```

#### GET /tags/{id}
Get a specific tag.

**Response 200:**
```json
{
  "id": "integer",
  "name": "string",
  "remaining_battery": "float",
  "packet_counter": "integer",
  "crew_member": {
    "id": "integer",
    "name": "string"
  } // null if unassigned
}
```

#### GET /tags/search
Search tags by exact name match.

**Query Parameters:**
- `name` (string, required): Exact tag name to search

**Response 200:**
```json
[
  {
    "id": "integer",
    "name": "string",
    "remaining_battery": "float"
  }
]
```

#### POST /tags
Create a new tag.

**Request Body:**
```json
{
  "name": "string",
  "crew_member_id": "integer" // optional
}
```

**Response 201:**
Same as GET /tags/{id}

#### PUT /tags/{id}
Update a tag.

**Request Body:**
```json
{
  "name": "string",
  "crew_member_id": "integer" // optional, null to unassign
}
```

**Response 200:**
Same as GET /tags/{id}

#### DELETE /tags/{id}
Delete a tag.

**Response 204:**
No content

---

### Entries Endpoints (Unassigned Tag Entries)

#### GET /entries
Get filtered list of unassigned tag entries.

**Query Parameters:**
- `start_timestamp` (datetime, optional): Filter by start timestamp
- `end_timestamp` (datetime, optional): Filter by end timestamp
- `shipyard_name` (string, optional): Filter by shipyard name (case-insensitive substring)
- `tag_name` (string, optional): Filter by exact tag name
- `skip` (integer, default: 0): Number of records to skip
- `limit` (integer, default: 50, max: 100 (for droplists)): Number of records to return

**Response 200:**
```json
{
  "items": [
    {
      "id": "integer",
      "tag": {
        "id": "integer",
        "name": "string",
        "remaining_battery": "float"
      },
      "shipyard": {
        "id": "integer",
        "name": "string"
      },
      "advertisement_timestamp": "datetime",
      "is_entering": "boolean"
    }
  ],
  "total": "integer"
}
```

#### DELETE /entries/{id}
Delete an unassigned tag entry.

**Response 204:**
No content

---

### Logs Endpoints (Permanence Logs)

#### GET /logs
Get filtered list of permanence logs.

**Query Parameters:**
- `start_timestamp` (datetime, optional): Filter by start timestamp
- `end_timestamp` (datetime, optional): Filter by end timestamp
- `shipyard_name` (string, optional): Filter by shipyard name (case-insensitive substring)
- `ship_name` (string, optional): Filter by ship name (case-insensitive substring)
- `crew_member_name` (string, optional): Filter by crew member name (case-insensitive substring)
- `skip` (integer, default: 0): Number of records to skip
- `limit` (integer, default: 50, max: 100 (for droplists)): Number of records to return

**Response 200:**
```json
{
  "items": [
    {
      "id": "integer",
      "crew_member": {
        "id": "integer",
        "name": "string",
        "role": {
          "id": "integer",
          "role_name": "string"
        },
        "ship": {
          "id": "integer",
          "name": "string"
        },
        "tag": {
          "id": "integer",
          "name": "string",
          "remaining_battery": "float"
        } // current tag, may be null
      },
      "shipyard": {
        "id": "integer",
        "name": "string"
      },
      "entry_timestamp": "datetime",    // either one of these two may be null, but never both
      "leave_timestamp": "datetime"     // either one of these two may be null, but never both
    }
  ],
  "total": "integer"
}
```

#### GET /logs/{id}
Get a specific permanence log.

**Response 200:**
```json
{
  "id": "integer",
  "crew_member_id": "integer",
  "shipyard_id": "integer",
  "entry_timestamp": "datetime",    // either one of these two may be null, but never both
  "leave_timestamp": "datetime",    // either one of these two may be null, but never both
  "crew_member": {
    "id": "integer",
    "name": "string",
    "role": {
      "id": "integer",
      "role_name": "string"
    },
    "ship": {
      "id": "integer",
      "name": "string"
    },
    "tag": {
      "id": "integer",
      "name": "string",
      "remaining_battery": "float"
    }
  },
  "shipyard": {
    "id": "integer",
    "name": "string"
  }
}
```

#### POST /logs
Create a new permanence log.

**Request Body:**
```json
{
  "crew_member_id": "integer",
  "shipyard_id": "integer",
  "entry_timestamp": "datetime",    // both are optional, but at least one must be given
  "leave_timestamp": "datetime"     // both are optional, but at least one must be given
}
```

**Response 201:**
Same as GET /logs/{id}

#### PUT /logs/{id}
Update a permanence log.

**Request Body:**
```json
{
  "crew_member_id": "integer",
  "entry_timestamp": "datetime",    // both are optional, but at least one must be given
  "leave_timestamp": "datetime"     // both are optional, but at least one must be given
}
```

**Response 200:**
Same as GET /logs/{id}

#### DELETE /logs/{id}
Delete a permanence log.

**Response 204:**
No content

---

### Advertisements Endpoint

#### POST /advertisements
Process a tag advertisement from the physical system.

Note: The exact request format and processing logic are still being determined 
based on the physical system integration requirements.

---

### Supporting Endpoints

#### GET /roles
Get all crew member roles.

**Response 200:**
```json
[
  {
    "id": "integer",
    "role_name": "string"
  }
]
```

#### GET /shipyards
Get all shipyards.

**Response 200:**
```json
[
  {
    "id": "integer",
    "name": "string"
  }
]
```

#### GET /activator-beacons
Get all activator beacons.

**Response 200:**
```json
[
  {
    "id": "integer",
    "number": "integer",
    "shipyard": {
      "id": "integer",
      "name": "string"
    },
    "is_first_when_entering": "boolean"
  }
]
```

---

### Common HTTP Status Codes

- **200** OK - Request succeeded
- **201** Created - Resource created successfully
- **204** No Content - Request succeeded with no response body
- **400** Bad Request - Invalid request parameters
- **401** Unauthorized - Missing or invalid authentication
- **403** Forbidden - Insufficient permissions
- **404** Not Found - Resource not found
- **422** Unprocessable Entity - Validation error
- **500** Internal Server Error - Server error

---

### Notes

1. All timestamps are in ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`
2. Pagination uses skip/limit pattern with default limit of 50 items
3. Droplist population uses limit pattern with the max limit, which is of 100 items
4. All text searches are case-insensitive substring matches unless specified
5. Tag name searches use exact match for reliability
6. The advertisement endpoint handles the complex logic of determining entry/exit based on beacon configuration
7. Unassigned tag entries are created when a tag not assigned to any crew member is detected
8. Battery percentages are represented as floats (0.0 to 100.0)

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

If the past beacon is from another shipyard than the current one, then the advertisement is to be ignored.

If the past beacon is the same as the current one, then the advertisement is to be ignored.

If either the past or the current beacon don't exist in the table, then the advertisement is to be ignored.

If the adverisement has past activator id equal to 0 then the advertisement is to be ignored, because 0 is the fallback value when there is no past beacon, and the implementation forces to have no beacon with id equal to zero.

#### Tags

If the tag name of the advertisement is not found in the table then a new Tag row is created in the db, taking the information from the advertisement, and continue processing the advertisement.

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

The base template roughly follows the paint drawing of it, that is an external part of this document.

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