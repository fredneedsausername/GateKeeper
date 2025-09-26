from flask import Flask, request, session, redirect, render_template, jsonify, flash
from waitress import serve
from psycopg.rows import dict_row
import os
from psycopg_pool import ConnectionPool
from functools import wraps
from datetime import datetime, timedelta
import base64
from typing import TypeVar, ParamSpec, Callable, Concatenate, Any

# Type variables for typing the decorator
P = ParamSpec('P')
R = TypeVar('R')
CursorType = Any

def auth_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect("/login")
        return fn(*args, **kwargs)
    return decorated

def get_env(env_var: str):
    ret = os.getenv(env_var)
    if not ret:
        raise Exception(f"{env_var} not found")
    return ret

db_url = get_env("DATABASE_URL")
db_pool = ConnectionPool(
    conninfo=db_url,
    min_size=4,
    max_size=20,
    timeout=30.0,
    configure=lambda conn: setattr(conn, 'row_factory', dict_row)
)

def connected_to_database(fn: Callable[Concatenate[CursorType, P], R]) -> Callable[P, R]:
    @wraps(fn)
    def wrapped_function(*args: P.args, **kwargs: P.kwargs) -> R:
        with db_pool.connection() as conn:
            with conn.cursor() as curs:
                ret = fn(curs, *args, **kwargs)
                conn.commit()
        return ret
    return wrapped_function

app = Flask(__name__)

@app.template_filter('b64encode')
def b64encode_filter(data):
    """Base64 encode filter for Jinja2"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.b64encode(data).decode('ascii')

@app.template_filter('datetime_format')
def datetime_format_filter(dt):
    """Format datetime for display"""
    if dt is None:
        return ''
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    return str(dt)

@app.context_processor
def inject_global_vars():
    return {
        'username': session.get("user", "Non riconosciuto"),
    }

secret_key = get_env("SECRET_KEY")
app.secret_key = str(secret_key)

# ===== UTILITY FUNCTIONS =====

@connected_to_database
def get_ships_for_dropdown(curs):
    curs.execute("SELECT id, name FROM ship ORDER BY name")
    ships = curs.fetchall()
    return [{"value": ship["id"], "label": ship["name"]} for ship in ships]

@connected_to_database
def get_roles_for_dropdown(curs):
    curs.execute("SELECT id, role_name FROM crew_member_roles ORDER BY role_name")
    roles = curs.fetchall()
    return [{"value": role["id"], "label": role["role_name"]} for role in roles]

@connected_to_database
def get_shipyards_for_dropdown(curs):
    curs.execute("SELECT id, name FROM shipyard ORDER BY name")
    shipyards = curs.fetchall()
    return [{"value": sy["id"], "label": sy["name"]} for sy in shipyards]

def get_filtered_data(table_type, filters, page=1, page_size=50):
    """Get filtered data based on table type and filters"""
    
    @connected_to_database
    def fetch_data(curs):
        if table_type == "crew_member":
            # Only show results if there are actual filters applied (not just empty strings)
            has_filters = any(v for v in filters.values() if v and str(v).strip())
            if not has_filters:
                return [], 0
                
            # Base query parts
            select_fields = """
                cm.id,
                cm.name as crew_member_name,
                cr.role_name,
                s.name as ship_name,
                t.mac_address as tag_name,
                t.remaining_battery as battery_level
            """
            
            from_where = """
                FROM crew_member cm
                LEFT JOIN crew_member_roles cr ON cm.role_id = cr.id
                LEFT JOIN ship s ON cm.ship_id = s.id
                LEFT JOIN tag t ON cm.tag_id = t.id
                WHERE 1=1
            """
            
            params = []
            filter_conditions = ""
            
            if filters.get('crew_name') and filters['crew_name'].strip():
                filter_conditions += " AND LOWER(cm.name) LIKE LOWER(%s)"
                params.append(f"%{filters['crew_name'].strip()}%")
            
            if filters.get('ship_name') and filters['ship_name'].strip():
                filter_conditions += " AND LOWER(s.name) LIKE LOWER(%s)"
                params.append(f"%{filters['ship_name'].strip()}%")
            
            if filters.get('role_id') and filters['role_id'].strip():
                filter_conditions += " AND cm.role_id = %s"
                params.append(int(filters['role_id']))
            
            if filters.get('ship_id') and filters['ship_id'].strip():
                filter_conditions += " AND cm.ship_id = %s"
                params.append(int(filters['ship_id']))
            
            # Count total
            count_query = f"SELECT COUNT(*) as count {from_where} {filter_conditions}"
            curs.execute(count_query, params)
            result = curs.fetchone()
            total = result['count'] if result else 0
            
            # Get data with pagination
            data_query = f"SELECT {select_fields} {from_where} {filter_conditions} ORDER BY cm.name LIMIT %s OFFSET %s"
            params.extend([page_size, (page - 1) * page_size])
            
            curs.execute(data_query, params)
            items = curs.fetchall()
            
            return items, total
            
        elif table_type == "ship":
            # Only show results if there is a filter applied (not just empty string)
            has_filters = any(v for v in filters.values() if v and str(v).strip())
            if not has_filters:
                return [], 0

            # Base query parts
            from_where = "FROM ship WHERE 1=1"
            params = []
            filter_conditions = ""
            
            if filters.get('ship_name') and filters['ship_name'].strip():
                filter_conditions += " AND LOWER(name) LIKE LOWER(%s)"
                params.append(f"%{filters['ship_name'].strip()}%")
            
            # Count total
            count_query = f"SELECT COUNT(*) as count {from_where} {filter_conditions}"
            curs.execute(count_query, params)
            result = curs.fetchone()
            total = result['count'] if result else 0
            
            # Get data with pagination
            data_query = f"SELECT id, name {from_where} {filter_conditions} ORDER BY name LIMIT %s OFFSET %s"
            params.extend([page_size, (page - 1) * page_size])
            
            curs.execute(data_query, params)
            items = curs.fetchall()
            
            return items, total
            
        elif table_type == "tag":
            # Base query parts
            select_fields = """
                t.id,
                t.mac_address as name,
                t.remaining_battery,
                cm.name as crew_member_name
            """
            
            from_where = """
                FROM tag t
                LEFT JOIN crew_member cm ON t.id = cm.tag_id
                WHERE 1=1
            """
            
            params = []
            filter_conditions = ""
            
            if filters.get('assigned') and not filters.get('vacant'):
                filter_conditions += " AND cm.id IS NOT NULL"
            elif filters.get('vacant') and not filters.get('assigned'):
                filter_conditions += " AND cm.id IS NULL"
            elif not filters.get('assigned') and not filters.get('vacant'):
                # No checkboxes selected - return empty
                return [], 0
            
            # Filter by tag name if provided
            if filters.get('tag_name') and filters['tag_name'].strip():
                filter_conditions += " AND LOWER(t.mac_address) LIKE LOWER(%s)"
                params.append(f"%{filters['tag_name'].strip()}%")
            
            # Count total
            count_query = f"SELECT COUNT(*) as count {from_where} {filter_conditions}"
            curs.execute(count_query, params)
            result = curs.fetchone()
            total = result['count'] if result else 0
            
            # Get data with pagination
            data_query = f"SELECT {select_fields} {from_where} {filter_conditions} ORDER BY t.remaining_battery ASC LIMIT %s OFFSET %s"
            params.extend([page_size, (page - 1) * page_size])
            
            curs.execute(data_query, params)
            items = curs.fetchall()
            
            return items, total
            
        elif table_type == "unassigned_tag_entry":
            # Base query parts
            select_fields = """
                ute.id,
                s.name as shipyard_name,
                t.mac_address as tag_name,
                t.remaining_battery as battery_level,
                ute.advertisement_timestamp,
                CASE WHEN ute.is_entering THEN 'Ingresso' ELSE 'Uscita' END as entry_type
            """
            
            from_where = """
                FROM unassigned_tag_entry ute
                JOIN tag t ON ute.tag_id = t.id
                JOIN shipyard s ON ute.shipyard_id = s.id
                WHERE 1=1
            """
            
            params = []
            filter_conditions = ""
            
            # Convert string timestamps to datetime objects if needed
            if filters.get('start_timestamp'):
                start_ts = filters['start_timestamp']
                if isinstance(start_ts, str):
                    try:
                        start_ts = datetime.fromisoformat(start_ts.replace('T', ' '))
                    except:
                        start_ts = datetime.now() - timedelta(hours=24)
                filter_conditions += " AND ute.advertisement_timestamp >= %s"
                params.append(start_ts)
            
            if filters.get('end_timestamp'):
                end_ts = filters['end_timestamp']
                if isinstance(end_ts, str):
                    try:
                        end_ts = datetime.fromisoformat(end_ts.replace('T', ' '))
                    except:
                        end_ts = datetime.now()
                filter_conditions += " AND ute.advertisement_timestamp <= %s"
                params.append(end_ts)
            
            if filters.get('shipyard_id') and filters['shipyard_id'].strip():
                filter_conditions += " AND ute.shipyard_id = %s"
                params.append(int(filters['shipyard_id']))
            
            if filters.get('tag_name') and filters['tag_name'].strip():
                filter_conditions += " AND LOWER(t.mac_address) LIKE LOWER(%s)"
                params.append(f"%{filters['tag_name'].strip()}%")
            
            # Count total
            count_query = f"SELECT COUNT(*) as count {from_where} {filter_conditions}"
            curs.execute(count_query, params)
            result = curs.fetchone()
            total = result['count'] if result else 0
            
            # Get data with pagination
            data_query = f"SELECT {select_fields} {from_where} {filter_conditions} ORDER BY ute.advertisement_timestamp DESC LIMIT %s OFFSET %s"
            params.extend([page_size, (page - 1) * page_size])
            
            curs.execute(data_query, params)
            items = curs.fetchall()
            
            return items, total
            
        elif table_type == "permanence_log":
            # Base query parts
            select_fields = """
                pl.id,
                s.name as shipyard_name,
                current_tag.mac_address as current_tag_name,
                current_tag.remaining_battery as current_battery_level,
                ship.name as ship_name,
                cm.name as crew_member_name,
                cr.role_name,
                pl.entry_timestamp,
                pl.leave_timestamp
            """
            
            from_where = """
                FROM permanence_log pl
                JOIN crew_member cm ON pl.crew_member_id = cm.id
                JOIN shipyard s ON pl.shipyard_id = s.id
                LEFT JOIN crew_member_roles cr ON cm.role_id = cr.id
                LEFT JOIN ship ship ON cm.ship_id = ship.id
                LEFT JOIN tag current_tag ON cm.tag_id = current_tag.id
                WHERE 1=1
            """
            
            params = []
            filter_conditions = ""
            
            # Convert string timestamps to datetime objects and apply time filters
            if filters.get('start_timestamp') and filters.get('end_timestamp'):
                start_ts = filters['start_timestamp']
                end_ts = filters['end_timestamp']
                
                if isinstance(start_ts, str):
                    try:
                        start_ts = datetime.fromisoformat(start_ts.replace('T', ' '))
                    except:
                        start_ts = datetime.now() - timedelta(hours=24)
                        
                if isinstance(end_ts, str):
                    try:
                        end_ts = datetime.fromisoformat(end_ts.replace('T', ' '))
                    except:
                        end_ts = datetime.now()
                
                filter_conditions += """
                    AND (
                        (pl.entry_timestamp <= %s AND (pl.leave_timestamp IS NULL OR pl.leave_timestamp >= %s))
                        OR (pl.entry_timestamp >= %s AND pl.entry_timestamp <= %s)
                    )
                """
                params.extend([end_ts, start_ts, start_ts, end_ts])
            
            if filters.get('shipyard_id') and filters['shipyard_id'].strip():
                filter_conditions += " AND pl.shipyard_id = %s"
                params.append(int(filters['shipyard_id']))
            
            if filters.get('ship_id') and filters['ship_id'].strip():
                filter_conditions += " AND cm.ship_id = %s"
                params.append(int(filters['ship_id']))
            
            if filters.get('crew_name') and filters['crew_name'].strip():
                filter_conditions += " AND LOWER(cm.name) LIKE LOWER(%s)"
                params.append(f"%{filters['crew_name'].strip()}%")
            
            # Count total
            count_query = f"SELECT COUNT(*) as count {from_where} {filter_conditions}"
            try:
                curs.execute(count_query, params)
                result = curs.fetchone()
                total = result['count'] if result else 0
            except Exception as e:
                print(f"Error in count query: {e}")
                print(f"Query: {count_query}")
                print(f"Params: {params}")
                total = 0
            
            # Get data with pagination
            data_query = f"SELECT {select_fields} {from_where} {filter_conditions} ORDER BY cm.name ASC LIMIT %s OFFSET %s"
            params_with_pagination = params + [page_size, (page - 1) * page_size]
            
            try:
                curs.execute(data_query, params_with_pagination)
                items = curs.fetchall()
            except Exception as e:
                print(f"Error in data query: {e}")
                print(f"Query: {data_query}")
                print(f"Params: {params_with_pagination}")
                items = []
            
            return items, total
            
        return [], 0
    
    return fetch_data()

# ===== HTMX TABLE CONFIG HELPER =====

def create_table_config(table_type, filters, page, request_path):
    """Helper function to create table configuration for both full and partial requests"""
    data, total_count = get_filtered_data(table_type, filters, page)
    
    if table_type == "crew_member":
        return {
            "title": "Gestione Crew",
            "description": "Visualizza e gestisci i membri dell'equipaggio",
            "columns": [
                {"key": "tag_name", "label": "Tag", "type": "text"},
                {"key": "battery_level", "label": "🔋%", "type": "battery"},
                {"key": "ship_name", "label": "Nave", "type": "text"},
                {"key": "crew_member_name", "label": "Equipaggio", "type": "text"},
                {"key": "role_name", "label": "Ruolo", "type": "text"}
            ],
            "text_filters": [
                {"key": "crew_name", "label": "Nome Equipaggio", "placeholder": "Cerca per nome..."}
            ],
            "searchable_select_filters": [
                {"key": "ship_id", "label": "Nave", "placeholder": "Cerca nave...", "search_endpoint": "/api/ships/filter"},
                {"key": "role_id", "label": "Ruolo", "placeholder": "Cerca ruolo...", "search_endpoint": "/api/roles/filter"}
            ],
            "allow_add": True,
            "allow_edit": True,
            "allow_delete": True,
            "add_button_text": "Aggiungi Crew",
            "empty_message": "Applica dei filtri per visualizzare i membri dell'equipaggio.",
            "add_url": "/crew/add",
            "edit_url": "/crew/edit/{id}",
            "delete_url": "/api/crew/delete/{id}",
            "data": data,
            "total_count": total_count,
            "page": page
        }
    
    elif table_type == "ship":
        return {
            "title": "Gestione Navi",
            "description": "Visualizza e gestisci le navi",
            "columns": [
                {"key": "name", "label": "Nave", "type": "text"}
            ],
            "text_filters": [
                {"key": "ship_name", "label": "Nome Nave", "placeholder": "Cerca per nome..."}
            ],
            "allow_add": True,
            "allow_edit": True,
            "allow_delete": True,
            "add_button_text": "Aggiungi Nave",
            "empty_message": "Applica dei filtri per visualizzare le navi.",
            "add_url": "/navi/add",
            "edit_url": "/navi/edit/{id}",
            "delete_url": "/api/ships/delete/{id}",
            "data": data,
            "total_count": total_count,
            "page": page
        }
    
    elif table_type == "tag":
        return {
            "title": "Gestione Tag",
            "description": "Visualizza e gestisci i tag",
            "columns": [
                {"key": "name", "label": "Tag", "type": "text"},
                {"key": "remaining_battery", "label": "🔋%", "type": "battery"},
                {"key": "crew_member_name", "label": "Equipaggio", "type": "text"}
            ],
            "text_filters": [
                {"key": "tag_name", "label": "Nome Tag", "placeholder": "Cerca per nome..."}
            ],
            "checkbox_filters": [
                {"key": "assigned", "label": "Assegnati"},
                {"key": "vacant", "label": "Vacanti"}
            ],
            "allow_add": True,
            "allow_edit": True,
            "allow_delete": True,
            "add_button_text": "Aggiungi Tag",
            "empty_message": "Seleziona almeno un filtro per visualizzare i tag.",
            "add_url": "/tag/add",
            "edit_url": "/tag/edit/{id}",
            "delete_url": "/api/tags/delete/{id}",
            "data": data,
            "total_count": total_count,
            "page": page
        }
    
    elif table_type == "unassigned_tag_entry":
        return {
            "title": "Entry dei Tag",
            "description": "Visualizza gli eventi dei tag non assegnati",
            "columns": [
                {"key": "shipyard_name", "label": "Cantiere", "type": "text"},
                {"key": "tag_name", "label": "Tag", "type": "text"},
                {"key": "battery_level", "label": "🔋%", "type": "battery"},
                {"key": "advertisement_timestamp", "label": "Passaggio", "type": "datetime"},
                {"key": "entry_type", "label": "Tipologia", "type": "text"}
            ],
            "date_filters": [
                {
                    "key": "start_timestamp", 
                    "label": "Data Inizio",
                    "default_value": (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
                },
                {
                    "key": "end_timestamp", 
                    "label": "Data Fine",
                    "default_value": datetime.now().strftime('%Y-%m-%dT%H:%M')
                }
            ],
            "searchable_select_filters": [
                {"key": "shipyard_id", "label": "Cantiere", "placeholder": "Cerca cantiere...", "search_endpoint": "/api/shipyards/filter"}
            ],
            "text_filters": [
                {"key": "tag_name", "label": "Nome Tag", "placeholder": "Cerca tag esatto..."}
            ],
            "allow_add": False,
            "allow_edit": False,
            "allow_delete": True,
            "empty_message": "Nessuna entry trovata nel periodo selezionato.",
            "delete_url": "/api/entries/delete/{id}",
            "data": data,
            "total_count": total_count,
            "page": page
        }
    
    elif table_type == "permanence_log":
        return {
            "title": "Log Permanenze",
            "description": "Visualizza i log di permanenza nei cantieri",
            "columns": [
                {"key": "shipyard_name", "label": "Cantiere", "type": "text"},
                {"key": "current_tag_name", "label": "Tag", "type": "text"},
                {"key": "current_battery_level", "label": "🔋%", "type": "battery"},
                {"key": "ship_name", "label": "Nave", "type": "text"},
                {"key": "crew_member_name", "label": "Equipaggio", "type": "text"},
                {"key": "role_name", "label": "Ruolo", "type": "text"},
                {"key": "entry_timestamp", "label": "Entrata", "type": "datetime"},
                {"key": "leave_timestamp", "label": "Uscita", "type": "datetime"}
            ],
            "date_filters": [
                {
                    "key": "start_timestamp", 
                    "label": "Data Inizio",
                    "default_value": (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
                },
                {
                    "key": "end_timestamp", 
                    "label": "Data Fine",
                    "default_value": datetime.now().strftime('%Y-%m-%dT%H:%M')
                }
            ],
            "searchable_select_filters": [
                {"key": "shipyard_id", "label": "Cantiere", "placeholder": "Cerca cantiere...", "search_endpoint": "/api/shipyards/filter"},
                {"key": "ship_id", "label": "Nave", "placeholder": "Cerca nave...", "search_endpoint": "/api/ships/filter"}
            ],
            "text_filters": [
                {"key": "crew_name", "label": "Nome Equipaggio", "placeholder": "Cerca per nome..."}
            ],
            "allow_add": True,
            "allow_edit": True,
            "allow_delete": True,
            "add_button_text": "Aggiungi Log",
            "empty_message": "Nessun log trovato nel periodo selezionato.",
            "add_url": "/log/add",
            "edit_url": "/log/edit/{id}",
            "delete_url": "/api/logs/delete/{id}",
            "data": data,
            "total_count": total_count,
            "page": page
        }

    return {
        "title": "Unknown Table",
        "description": "",
        "columns": [],
        "data": data,
        "total_count": total_count,
        "page": page
    }

# ===== MAIN ROUTES =====

@app.route("/")
@auth_required
def index():
    return redirect("/log")

@app.route("/login", methods=["GET"])
def login_get():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
@connected_to_database
def login_post(curs):
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    curs.execute("SELECT username FROM users WHERE username=%s AND password=%s", (username, password))
    user = curs.fetchone()
    if user:
        session["user"] = username
        return jsonify({
            "message": "Login effettuato con successo",
            "redirect": "/"
        }), 200
    else:
        return jsonify({
            "error": "Credenziali incorrette"
        }), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===== CREW MEMBERS ROUTES WITH HTMX =====

@app.route('/crew')
@app.route('/crew/partial')
@auth_required
def crew_page():
    # Get filters from URL parameters
    filters = {
        'crew_name': request.args.get('crew_name', ''),
        'ship_name': request.args.get('ship_name', ''),
        'role_id': request.args.get('role_id', ''),
        'ship_id': request.args.get('ship_id', '')
    }
    
    page = int(request.args.get('page', 1))
    
    try:
        table_config = create_table_config("crew_member", filters, page, request.path)
    except Exception as e:
        print(f"Error in crew_page: {e}")
        table_config = create_table_config("crew_member", {}, 1, request.path)
    
    # Return partial template for HTMX requests
    if request.path.endswith('/partial'):
        return render_template('table_content_partial.html', table_config=table_config)
    
    # Return full page for regular requests
    return render_template('crew.html', table_config=table_config)

@app.route('/crew/add', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def add_crew(curs):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            ship_id = request.form.get('ship_id') or None
            role_id = request.form.get('role_id') or None
            tag_id = request.form.get('tag_id') or None
            if not name:
                flash('Nome è obbligatorio', 'error')
                return redirect(request.url)
            # Enforce that a tag can only be assigned to one crew member
            if tag_id:
                curs.execute("SELECT COUNT(*) as count FROM crew_member WHERE tag_id = %s", [tag_id])
                result = curs.fetchone()
                if result and result['count'] > 0:
                    flash('Tag già assegnato a un altro membro dell\'equipaggio', 'error')
                    return redirect(request.url)
            curs.execute(
                "INSERT INTO crew_member (name, ship_id, role_id, tag_id) VALUES (%s, %s, %s, %s)",
                [name, ship_id, role_id, tag_id]
            )
            flash('Crew member aggiunto con successo', 'success')
            return redirect('/crew')
        except Exception as e:
            flash(f'Errore durante l\'aggiunta: {str(e)}', 'error')
            return redirect(request.url)
    return render_template('crew_add.html')

@app.route('/crew/edit/<int:crew_id>', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def edit_crew(curs, crew_id):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            ship_id = request.form.get('ship_id') or None
            role_id = request.form.get('role_id') or None
            tag_id = request.form.get('tag_id') or None
            if not name:
                flash('Nome è obbligatorio', 'error')
                return redirect(request.url)
            # Enforce that a tag can only be assigned to one crew member except itself
            if tag_id:
                curs.execute("SELECT COUNT(*) as count FROM crew_member WHERE tag_id = %s AND id != %s", [tag_id, crew_id])
                result = curs.fetchone()
                if result and result['count'] > 0:
                    flash('Tag già assegnato a un altro membro dell\'equipaggio', 'error')
                    return redirect(request.url)
            curs.execute(
                "UPDATE crew_member SET name = %s, ship_id = %s, role_id = %s, tag_id = %s WHERE id = %s",
                [name, ship_id, role_id, tag_id, crew_id]
            )
            flash('Crew member aggiornato con successo', 'success')
            return redirect('/crew')
        except Exception as e:
            flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
            return redirect(request.url)
    # GET request
    curs.execute(
        """SELECT cm.*, s.name as ship_name, cr.role_name, t.name as tag_name
           FROM crew_member cm
           LEFT JOIN ship s ON cm.ship_id = s.id
           LEFT JOIN crew_member_roles cr ON cm.role_id = cr.id
           LEFT JOIN tag t ON cm.tag_id = t.id
           WHERE cm.id = %s""",
        [crew_id]
    )
    crew_member = curs.fetchone()
    if not crew_member:
        flash('Crew member non trovato', 'error')
        return redirect('/crew')
    return render_template('crew_edit.html', crew_member=crew_member)

@app.route('/api/crew/delete/<int:crew_id>', methods=['DELETE'])
@auth_required
@connected_to_database
def delete_crew(curs, crew_id):
    try:
        curs.execute("DELETE FROM crew_member WHERE id = %s", [crew_id])
        return jsonify({"success": True, "message": "Crew member eliminato con successo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== SHIPS ROUTES WITH HTMX =====

@app.route('/navi')
@app.route('/navi/partial')
@auth_required
def ships_page():
    # Get filters from URL parameters
    filters = {
        'ship_name': request.args.get('ship_name', '')
    }
    
    page = int(request.args.get('page', 1))
    
    try:
        table_config = create_table_config("ship", filters, page, request.path)
    except Exception as e:
        print(f"Error in ships_page: {e}")
        table_config = create_table_config("ship", {}, 1, request.path)
    
    # Return partial template for HTMX requests
    if request.path.endswith('/partial'):
        return render_template('table_content_partial.html', table_config=table_config)
    
    # Return full page for regular requests
    return render_template('ships.html', table_config=table_config)

@app.route('/navi/add', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def add_ship(curs):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            if not name:
                flash('Nome è obbligatorio', 'error')
                return redirect(request.url)
            curs.execute("INSERT INTO ship (name) VALUES (%s)", [name])
            flash('Nave aggiunta con successo', 'success')
            return redirect('/navi')
        except Exception as e:
            flash(f'Errore durante l\'aggiunta: {str(e)}', 'error')
            return redirect(request.url)
    return render_template('ship_add.html')

@app.route('/navi/edit/<int:ship_id>', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def edit_ship(curs, ship_id):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            if not name:
                flash('Nome è obbligatorio', 'error')
                return redirect(request.url)
            curs.execute("UPDATE ship SET name = %s WHERE id = %s", [name, ship_id])
            flash('Nave aggiornata con successo', 'success')
            return redirect('/navi')
        except Exception as e:
            flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
            return redirect(request.url)
    # GET request
    curs.execute("SELECT * FROM ship WHERE id = %s", [ship_id])
    ship = curs.fetchone()
    if not ship:
        flash('Nave non trovata', 'error')
        return redirect('/navi')
    return render_template('ship_edit.html', ship=ship)

@app.route('/api/ships/delete/<int:ship_id>', methods=['DELETE'])
@auth_required
@connected_to_database
def delete_ship(curs, ship_id):
    try:
        curs.execute("DELETE FROM ship WHERE id = %s", [ship_id])
        return jsonify({"success": True, "message": "Nave eliminata con successo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== TAGS ROUTES WITH HTMX =====

@app.route('/tag')
@app.route('/tag/partial')
@auth_required
def tags_page():
    # Default both Vacanti and Assegnati when no checkboxes selected
    if not request.args.get('assigned') and not request.args.get('vacant') and not request.path.endswith('/partial'):
        return redirect(f"{request.path}?assigned=1&vacant=1")
    # Get filters from URL parameters
    filters = {
        'assigned': request.args.get('assigned'),
        'vacant': request.args.get('vacant'),
        'tag_name': request.args.get('tag_name', '').strip()
    }
    
    page = int(request.args.get('page', 1))
    
    try:
        table_config = create_table_config("tag", filters, page, request.path)
    except Exception as e:
        print(f"Error in tags_page: {e}")
        table_config = create_table_config("tag", {}, 1, request.path)
    
    # Return partial template for HTMX requests
    if request.path.endswith('/partial'):
        return render_template('table_content_partial.html', table_config=table_config)
    
    # Return full page for regular requests
    return render_template('tags.html', table_config=table_config)

@app.route('/tag/add', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def add_tag(curs):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            crew_member_id = request.form.get('crew_member_id') or None
            
            if not name:
                flash('Nome tag è obbligatorio', 'error')
                return redirect(request.url)
            # Insert tag
            curs.execute("INSERT INTO tag (name, remaining_battery, packet_counter) VALUES (%s, %s, %s)", [name, 100.0, 0])
            # Get the new tag ID
            curs.execute("SELECT id FROM tag WHERE name = %s ORDER BY id DESC LIMIT 1", [name])
            tag_id = curs.fetchone()['id']
            # If crew member selected, assign tag to them
            if crew_member_id:
                curs.execute("UPDATE crew_member SET tag_id = %s WHERE id = %s", [tag_id, crew_member_id])
            flash('Tag aggiunto con successo', 'success')
            return redirect('/tag')
        except Exception as e:
            flash(f'Errore durante l\'aggiunta: {str(e)}', 'error')
            return redirect(request.url)
    return render_template('tag_add.html')

@app.route('/tag/edit/<int:tag_id>', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def edit_tag(curs, tag_id):
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            crew_member_id = request.form.get('crew_member_id') or None
            
            if not name:
                flash('Nome tag è obbligatorio', 'error')
                return redirect(request.url)
            
            # Update tag name
            curs.execute("UPDATE tag SET name = %s WHERE id = %s", [name, tag_id])
            # Remove tag from current crew member
            curs.execute("UPDATE crew_member SET tag_id = NULL WHERE tag_id = %s", [tag_id])
            # Assign to new crew member if selected
            if crew_member_id:
                curs.execute("UPDATE crew_member SET tag_id = %s WHERE id = %s", [tag_id, crew_member_id])
            flash('Tag aggiornato con successo', 'success')
            return redirect('/tag')
        except Exception as e:
            flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
            return redirect(request.url)
    # GET request
    curs.execute(
        """SELECT t.*, cm.name as crew_member_name, cm.id as crew_member_id
           FROM tag t
           LEFT JOIN crew_member cm ON t.id = cm.tag_id
           WHERE t.id = %s""",
        [tag_id]
    )
    tag = curs.fetchone()
    if not tag:
        flash('Tag non trovato', 'error')
        return redirect('/tag')
    return render_template('tag_edit.html', tag=tag)

@app.route('/api/tags/delete/<int:tag_id>', methods=['DELETE'])
@auth_required
@connected_to_database
def delete_tag(curs, tag_id):
    try:
        curs.execute("DELETE FROM tag WHERE id = %s", [tag_id])
        return jsonify({"success": True, "message": "Tag eliminato con successo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== ENTRIES ROUTES WITH HTMX =====

@app.route('/entry')
@app.route('/entry/partial')
@auth_required
def entries_page():
    # Default to last 24 hours if no dates specified
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    # Get filters from URL parameters with proper defaults
    filters = {
        'start_timestamp': request.args.get('start_timestamp', yesterday.strftime('%Y-%m-%dT%H:%M')),
        'end_timestamp': request.args.get('end_timestamp', now.strftime('%Y-%m-%dT%H:%M')),
        'shipyard_id': request.args.get('shipyard_id', ''),
        'tag_name': request.args.get('tag_name', '')
    }
    
    page = int(request.args.get('page', 1))
    
    try:
        table_config = create_table_config("unassigned_tag_entry", filters, page, request.path)
    except Exception as e:
        print(f"Error in entries_page: {e}")
        table_config = create_table_config("unassigned_tag_entry", {}, 1, request.path)
    
    # Return partial template for HTMX requests
    if request.path.endswith('/partial'):
        return render_template('table_content_partial.html', table_config=table_config)
    
    # Return full page for regular requests
    return render_template('entries.html', table_config=table_config)

@app.route('/api/entries/delete/<int:entry_id>', methods=['DELETE'])
@auth_required
@connected_to_database
def delete_entry(curs, entry_id):
    try:
        curs.execute("DELETE FROM unassigned_tag_entry WHERE id = %s", [entry_id])
        return jsonify({"success": True, "message": "Entry eliminata con successo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== LOGS ROUTES WITH HTMX =====

@app.route('/log')
@app.route('/log/partial')
@auth_required
def logs_page():
    # Default to last 24 hours if no dates specified
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    # Get filters from URL parameters with proper defaults
    filters = {
        'start_timestamp': request.args.get('start_timestamp', yesterday.strftime('%Y-%m-%dT%H:%M')),
        'end_timestamp': request.args.get('end_timestamp', now.strftime('%Y-%m-%dT%H:%M')),
        'shipyard_id': request.args.get('shipyard_id', ''),
        'ship_id': request.args.get('ship_id', ''),
        'crew_name': request.args.get('crew_name', '')
    }
    
    page = int(request.args.get('page', 1))
    
    try:
        table_config = create_table_config("permanence_log", filters, page, request.path)
    except Exception as e:
        print(f"Error in logs_page: {e}")
        table_config = create_table_config("permanence_log", {}, 1, request.path)
    
    # Return partial template for HTMX requests
    if request.path.endswith('/partial'):
        return render_template('table_content_partial.html', table_config=table_config)
    
    # Return full page for regular requests
    return render_template('logs.html', table_config=table_config)

@app.route('/log/add', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def add_log(curs):
    if request.method == 'POST':
        try:
            crew_member_id = request.form.get('crew_member_id')
            shipyard_id = request.form.get('shipyard_id')
            entry_timestamp = request.form.get('entry_timestamp') or None
            leave_timestamp = request.form.get('leave_timestamp') or None
            if not crew_member_id or not shipyard_id:
                flash('Crew member e cantiere sono obbligatori', 'error')
                return redirect(request.url)
            if not entry_timestamp and not leave_timestamp:
                flash('Almeno una data (entrata o uscita) è obbligatoria', 'error')
                return redirect(request.url)
            curs.execute(
                "INSERT INTO permanence_log (crew_member_id, shipyard_id, entry_timestamp, leave_timestamp) VALUES (%s, %s, %s, %s)",
                [crew_member_id, shipyard_id, entry_timestamp, leave_timestamp]
            )
            flash('Log aggiunto con successo', 'success')
            return redirect('/log')
        except Exception as e:
            flash(f'Errore durante l\'aggiunta: {str(e)}', 'error')
            return redirect(request.url)
    return render_template('log_add.html')

@app.route('/log/edit/<int:log_id>', methods=['GET', 'POST'])
@auth_required
@connected_to_database
def edit_log(curs, log_id):
    if request.method == 'POST':
        try:
            crew_member_id = request.form.get('crew_member_id')
            entry_timestamp = request.form.get('entry_timestamp') or None
            leave_timestamp = request.form.get('leave_timestamp') or None
            if not crew_member_id:
                flash('Crew member è obbligatorio', 'error')
                return redirect(request.url)
            if not entry_timestamp and not leave_timestamp:
                flash('Almeno una data (entrata o uscita) è obbligatoria', 'error')
                return redirect(request.url)
            curs.execute(
                "UPDATE permanence_log SET crew_member_id = %s, entry_timestamp = %s, leave_timestamp = %s WHERE id = %s",
                [crew_member_id, entry_timestamp, leave_timestamp, log_id]
            )
            flash('Log aggiornato con successo', 'success')
            return redirect('/log')
        except Exception as e:
            flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
            return redirect(request.url)
    # GET request
    curs.execute(
        """SELECT pl.*, cm.name as crew_member_name, s.name as shipyard_name
           FROM permanence_log pl
           JOIN crew_member cm ON pl.crew_member_id = cm.id
           JOIN shipyard s ON pl.shipyard_id = s.id
           WHERE pl.id = %s""",
        [log_id]
    )
    log = curs.fetchone()
    if not log:
        flash('Log non trovato', 'error')
        return redirect('/log')
    return render_template('log_edit.html', log=log)

@app.route('/api/logs/delete/<int:log_id>', methods=['DELETE'])
@auth_required
@connected_to_database
def delete_log(curs, log_id):
    try:
        curs.execute("DELETE FROM permanence_log WHERE id = %s", [log_id])
        return jsonify({"success": True, "message": "Log eliminato con successo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== SEARCH ENDPOINTS (keep for add/edit forms) =====

@app.route('/api/ships/search', methods=['POST'])
@auth_required
@connected_to_database
def search_ships(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, name FROM ship WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 10",
        [f"%{query}%"]
    )
    ships = curs.fetchall()
    
    return jsonify({"ships": ships})

@app.route('/api/roles/search', methods=['POST'])
@auth_required
@connected_to_database
def search_roles(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, role_name FROM crew_member_roles WHERE LOWER(role_name) LIKE LOWER(%s) ORDER BY role_name LIMIT 10",
        [f"%{query}%"]
    )
    roles = curs.fetchall()
    
    return jsonify({"roles": roles})

@app.route('/api/tags/search', methods=['POST'])
@auth_required
@connected_to_database
def search_tags(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    current_tag_id = data.get('current_tag_id') or None

    # Search only unassigned tags, but include the current tag if editing
    params = [f"%{query}%"]
    subquery = "SELECT tag_id FROM crew_member WHERE tag_id IS NOT NULL"
    if current_tag_id:
        sql = (
            "SELECT t.id, t.name "
            "FROM tag t "
            "WHERE LOWER(t.name) LIKE LOWER(%s) "
            "  AND (t.id = %s OR t.id NOT IN (" + subquery + ")) "
            "ORDER BY t.name LIMIT 10"
        )
        params.append(current_tag_id)
    else:
        sql = (
            "SELECT t.id, t.name "
            "FROM tag t "
            "WHERE LOWER(t.name) LIKE LOWER(%s) "
            "  AND t.id NOT IN (" + subquery + ") "
            "ORDER BY t.name LIMIT 10"
        )
    curs.execute(sql, params)
    tags = curs.fetchall()
    return jsonify({"tags": tags})

@app.route('/api/crew/search', methods=['POST'])
@auth_required
@connected_to_database
def search_crew(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, name FROM crew_member WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 10",
        [f"%{query}%"]
    )
    crew_members = curs.fetchall()
    
    return jsonify({"crew_members": crew_members})

@app.route('/api/shipyards/search', methods=['POST'])
@auth_required
@connected_to_database
def search_shipyards(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, name FROM shipyard WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 10",
        [f"%{query}%"]
    )
    shipyards = curs.fetchall()
    
    return jsonify({"shipyards": shipyards})

# ===== NEW FILTER SEARCH ENDPOINTS =====

@app.route('/api/ships/filter', methods=['POST'])
@auth_required
@connected_to_database
def filter_ships(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    selected_id = data.get('selected_id')
    
    # If we have a selected_id but no query, return just that item
    if selected_id and not query:
        curs.execute("SELECT id, name FROM ship WHERE id = %s", [selected_id])
        ship = curs.fetchone()
        if ship:
            return jsonify({"options": [{"value": ship["id"], "label": ship["name"]}]})
        return jsonify({"options": []})
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, name FROM ship WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 10",
        [f"%{query}%"]
    )
    ships = curs.fetchall()
    
    options = [{"value": ship["id"], "label": ship["name"]} for ship in ships]
    return jsonify({"options": options})

@app.route('/api/roles/filter', methods=['POST'])
@auth_required
@connected_to_database
def filter_roles(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    selected_id = data.get('selected_id')
    
    # If we have a selected_id but no query, return just that item
    if selected_id and not query:
        curs.execute("SELECT id, role_name FROM crew_member_roles WHERE id = %s", [selected_id])
        role = curs.fetchone()
        if role:
            return jsonify({"options": [{"value": role["id"], "label": role["role_name"]}]})
        return jsonify({"options": []})
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, role_name FROM crew_member_roles WHERE LOWER(role_name) LIKE LOWER(%s) ORDER BY role_name LIMIT 10",
        [f"%{query}%"]
    )
    roles = curs.fetchall()
    
    options = [{"value": role["id"], "label": role["role_name"]} for role in roles]
    return jsonify({"options": options})

@app.route('/api/shipyards/filter', methods=['POST'])
@auth_required
@connected_to_database
def filter_shipyards(curs):
    data = request.get_json()
    query = data.get('query', '').strip()
    selected_id = data.get('selected_id')
    
    # If we have a selected_id but no query, return just that item
    if selected_id and not query:
        curs.execute("SELECT id, name FROM shipyard WHERE id = %s", [selected_id])
        shipyard = curs.fetchone()
        if shipyard:
            return jsonify({"options": [{"value": shipyard["id"], "label": shipyard["name"]}]})
        return jsonify({"options": []})
    
    # Remove the 2-character minimum requirement
    curs.execute(
        "SELECT id, name FROM shipyard WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 10",
        [f"%{query}%"]
    )
    shipyards = curs.fetchall()
    
    options = [{"value": shipyard["id"], "label": shipyard["name"]} for shipyard in shipyards]
    return jsonify({"options": options})

# import json
# @app.route('/gateway-endpoint', methods=['POST'])
# def gateway_endpoint():
#     # Dump to log
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     log_file_path = os.path.join(script_dir, 'beacon_dump.txt')
    
#     try:
#         with open(log_file_path, 'a', encoding='utf-8') as f:
#             json_data = request.json
            
#             if json_data:
#                 f.write("JSON received:\n")
#                 f.write(json.dumps(json_data, indent=4))
#                 f.write("\n\n")
#             else:
#                 processed_data = request.get_data().decode('utf-8')
#                 f.write(processed_data)
#                 f.write("\n\n")
        
#         return "Data logged successfully", 200
            
#     except Exception as e:
#         # Fallback to console if file writing fails
#         print(f"Error writing to log file: {e}")
#         json_data = request.json
#         if json_data:
#             print("JSON received:")
#             print(json.dumps(json_data, indent=2))
#         else:
#             processed_data = request.get_data().decode('utf-8')
#             print(processed_data)
        
#         return "Error logging data", 500




# script_dir = os.path.dirname(os.path.abspath(__file__))
# log_file_path = os.path.join(script_dir, 'beacon_dump.txt')
# import threading
# log_lock = threading.Lock()
# beacon_dump_writer = open(log_file_path, 'a', encoding='utf-8')

# with log_lock:
#         beacon_dump_writer.write("mac         |echo |rssi (dbm)|count\n")
#         beacon_dump_writer.write("------------+-----+----------+-----\n")
#         beacon_dump_writer.flush()

# def print_formatted_data(mac, echo, rssi, count):
#     with log_lock:
#         beacon_dump_writer.write(f"{mac}|{echo.ljust(5)}|{rssi.ljust(10)}|{count.ljust(5)}\n")
#         beacon_dump_writer.flush()

# @app.route('/gateway-endpoint', methods=['POST'])
# def gateway_endpoint():
#     json_data = request.json

#     data = json_data.get("data")
#     if not data:
#         return "Invalid gateway message", 400

#     value = data.get("value")
#     if not value:
#         return "Invalid gateway message", 400
    
#     device_list = value.get("device_list")
#     if not device_list:
#         return "Invalid gateway message", 400
    
#     for device in device_list:
        
#         device_data = device.get("data")
#         if not device_data:
#             return "Invalid gateway message", 400
        
#         device_data = device_data[16:] # Skip header

#         unprocessed_echobeacon_id = device_data[:4]
#         packet_type = device_data[4:6]
#         packet_counter = device_data[6:8]
#         mac_address = device_data[8:20]
#         unprocessed_rssi = device_data[20:22]

#         # Only consider echo packets
#         if packet_type != "03":
#             continue

#         echobeacon_id = str(int(unprocessed_echobeacon_id, 16))
#         rssi_dbm = str(int(unprocessed_rssi, 16) - 256)

#         print_formatted_data(mac_address, echobeacon_id, rssi_dbm, packet_counter)
    
#     return "Processed correctly", 200




# Used to determine remaining battery percentage
BATTERY_MAX_MILLIVOLTS = 3000

@connected_to_database
def process_device(curs, device):

    device_data = device.get("data")
    if not device_data:
        return # Invalid gateway message

    device_data = device_data[16:] # Skip header

    # Here device_data is a payload like 0001030F0C2A6F8A9289D1000000000000000000000000

    # Consider only presence packets
    message_type = device_data[4:6]
    if message_type != "03":
        return
    
    # Consider only Eddystone TLM packets
    packet_payload = int(device_data[22:24], 16)
    if not (packet_payload & 0x04):
        return

    beacon_mac_address = device_data[8:20]

    packet_counter = int(device_data[6:8], 16)

    # Compute remaining battery percentage
    eddy_volt = int(device_data[24:28], 16) 
    remaining_battery_percentage = round(eddy_volt / BATTERY_MAX_MILLIVOLTS, 1)

    # Get packet counter for current beacon
    # We also get the previous_echobeacon for future use, and we put it all in this query for efficiency in this critical server endpoint
    curs.execute("""
        SELECT id, packet_counter, previous_echobeacon
        FROM tag
        WHERE mac_address = %s
    """, (beacon_mac_address,))

    fetched = curs.fetchone()

    # Register unknown tag when system comes in contact with it
    if not fetched:

        curs.execute("""
            INSERT INTO tag (mac_address, remaining_battery, packet_counter)
            VALUES (%s, %s, %s)
        """, (beacon_mac_address, remaining_battery_percentage, packet_counter))

        # If this is the first time that the device passed through the system, then no direction can be inferred. Thus,
        # it makes no sense to process it any further
        return

    # Can be None. If it is, no problem at all. Simply means that there is no exclusion based on packet counter number to be made
    fetched_packet_counter = fetched.get("packet_counter")
    
    # Can be None. Later we'll ensure that if it is, then we ignore the message
    previous_echobeacon = fetched.get("previous_echobeacon")

    # For future use
    beacon_id = fetched.get("id")

    # If the message is repeated, then skip the read
    if packet_counter == fetched_packet_counter:
        return

    echobeacon_id = int(device_data[0:4], 16)

    # Update packet counter and last activator beacon
    # We already cached the true value of the previous activator beacon into the variable "previous_echobeacon"
    curs.execute("""
        UPDATE tag
        SET
            packet_counter = %s,
            previous_echobeacon = (
                SELECT id
                FROM activator_beacon
                WHERE friendly_number = %s
            ),
            remaining_battery = %s
        WHERE mac_address = %s;
    """, (packet_counter, echobeacon_id, remaining_battery_percentage, beacon_mac_address))

    # Now we have ensured that the message is original, and that all the preprocessing has taken place

    # ----- PROCESS MESSAGE -----

    # We exclude messages that don't have a previous echobeacon, because no direction can be inferred
    if not previous_echobeacon:
        return

    # We exclude messages where the previous echobeacon and the current one are the same
    if previous_echobeacon == echobeacon_id:
        return
    
    # We get info about the activator beacons to use it in the message processing steps
    curs.execute("""
        SELECT shipyard_id, is_first_when_entering
        FROM activator_beacon
        WHERE friendly_number = %s
    """, (echobeacon_id,))

    fetched = curs.fetchone()

    # If the echobeacon is not registered, skip processing. We assume that all echobeacons are correctly registered,
    # so if a message comes from an unrecognized echobeacon it's not something that has to do with us.
    if not fetched: 
        return

    current_shipyard_id = fetched.get("shipyard_id")                        # Not null and without defaults
    current_is_first_when_entering = fetched.get("is_first_when_entering")  # Not null and without defaults

    # We get the shipyard of the previous echobeacon, to compare it with the current one
    # We can deduce the direction information without is_first_when_entering
    curs.execute("""
        SELECT shipyard_id
        FROM activator_beacon
        WHERE friendly_number = %s
    """, (previous_echobeacon,))

    fetched = curs.fetchone()

    # If the previous activator beacon got eliminated in the meanwhile, skip processing. That's because
    # we cannot deduce a direction.
    if not fetched:
        return

    previous_shipyard_id = fetched.get("shipyard_id")

    # If the previous echobeacon comes from a different shipyard, it makes no sense to deduce a direction out of it
    if current_shipyard_id != previous_shipyard_id:
        return
    
    # Now we are sure that the activator beacons are different and from the same shipyard: we can deduce a direction.
    is_direction_entering = None

    if current_is_first_when_entering:
        is_direction_entering = False
    else:
        is_direction_entering = True

    # ----- DETERMINE EVENT TYPE (entry or log) -----

    is_entry = None

    curs.execute("""
        SELECT id
        FROM crew_member
        WHERE tag_id = %s
    """, (beacon_id,))

    fetched = curs.fetchone()

    # If no crew member has ownership of the tag, then it is an unassigned tag entry, else it is a log
    if not fetched:
        is_entry = True
    else:
        is_entry = False
        crew_member_id = fetched.get("id")
    
    # --- Register event in database ---

    if is_entry:
        curs.execute("""
            INSERT INTO unassigned_tag_entry (tag_id, shipyard_id, is_entering)
            VALUES (%s, %s, %s)
        """, (beacon_id, current_shipyard_id, is_direction_entering))

        # Finished processing
        return
    
    else:

        # Check if the most recent log of the crew member, that is from the same shipyard exists, is open, or closed
        curs.execute("""
            SELECT entry_timestamp, leave_timestamp
            FROM permanence_log
            WHERE
                shipyard_id = %s AND
                crew_member_id = %s
            ORDER BY GREATEST(entry_timestamp, leave_timestamp) DESC NULLS LAST
            LIMIT 1;
        """, (current_shipyard_id, crew_member_id))

        # To understand whether the log is open or closed we look at the timestamps

        fetched = curs.fetchone()

        exists = bool(fetched)

        if exists:
            is_closed = bool(fetched.get("leave_timestamp"))

        if is_direction_entering:
            curs.execute("""
                INSERT INTO permanence_log (
                    crew_member_id,
                    shipyard_id,
                    entry_timestamp
                ) VALUES (
                    %s,
                    %s,
                    NOW()
                )
            """, (crew_member_id, current_shipyard_id))
        else:
            # We infer that it is open, using a short-circuit evalutation
            if exists and (not is_closed):
                curs.execute("""
                    UPDATE permanence_log
                    SET leave_timestamp = NOW()
                    WHERE id = (
                        SELECT id
                        FROM permanence_log
                        WHERE
                            crew_member_id = %s AND
                            shipyard_id = %s
                        ORDER BY GREATEST(entry_timestamp, leave_timestamp) DESC NULLS LAST
                        LIMIT 1;
                    )
                """)
            else:
                curs.execute("""
                    INSERT INTO permanence_log (
                        crew_member_id,
                        shipyard_id,
                        leave_timestamp
                    ) VALUES (
                        %s,
                        %s,
                        NOW()
                    )
                """, (crew_member_id, current_shipyard_id))

        return

@app.route('/gateway-endpoint', methods=['POST'])
def gateway_endpoint():

    json_data = request.json

    data = json_data.get("data")
    if not data:
        return "Invalid gateway message", 400

    value = data.get("value")
    if not value:
        return "Invalid gateway message", 400
    
    device_list = value.get("device_list")
    if not device_list:
        return "Invalid gateway message", 400
    
    # From here on out the order of the lines of code is quirky
    # This is intentional: things appear in the order that makes for the fastest execution
    # That can only be done if we study the order of the instructions to make the ones that command the exit conditions first

    for device in device_list:
        process_device(device)

    return "Processed", 200


if __name__ == "__main__":
    flask_env = get_env("FLASK_ENV")
    flask_port = int(get_env("FLASK_PORT"))

    match flask_env:
        case "development":
            while True:
                try:
                    app.run(debug=True, port=flask_port, host="0.0.0.0")
                except SystemExit:
                    db_pool.close(timeout=0)
        case "production":
            serve(app, port=flask_port, host="0.0.0.0")
        case _:
            raise Exception(f"{flask_env} must be either \"development\" or \"production\"")