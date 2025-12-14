from flask import  render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash  # 用于密码加密
import datetime
from datetime import timedelta
import logging
from flask import Flask

logging.basicConfig(level=logging.ERROR)
app = Flask(__name__)

app.secret_key = 'your_secure_secret_key_here_123'  # 用于session加密，建议修改为随机字符串
DATABASE = 'book_system.db'  # 数据库文件

# 确保静态文件和模板目录存在
if not os.path.exists('static'):
    os.makedirs('static')
if not os.path.exists('static/images'):
    os.makedirs('static/images')
if not os.path.exists('templates'):
    os.makedirs('templates')


# 连接数据库
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # 允许通过列名访问数据
    return conn


# 初始化数据库（首次运行时自动创建表）
def init_db():
    with app.app_context():
        db = get_db()
        # 创建用户表（密码字段改为存储加密后的哈希值）
        db.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,  --存储加密后的密码
            name TEXT NOT NULL,
            identity TEXT NOT NULL,  --student/admin
            id_card TEXT NOT NULL,
            phone TEXT,
            status INTEGER DEFAULT 1  --1:正常, 0:冻结
        )
        ''')
        # 创建图书分类表
        db.execute('''
        CREATE TABLE IF NOT EXISTS book_category (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
        ''')
        # 创建图书表
        db.execute('''
        CREATE TABLE IF NOT EXISTS book (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            publisher TEXT NOT NULL,
            publish_date TEXT NOT NULL,
            category_id INTEGER,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            cover TEXT,  -- 封面路径
            description TEXT,
            FOREIGN KEY (category_id) REFERENCES book_category(id)
        )
        ''')
        # 创建借阅记录表
        db.execute('''
        CREATE TABLE IF NOT EXISTS borrow_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            borrow_time TEXT NOT NULL,
            due_time TEXT NOT NULL,
            return_time TEXT,
            renew_count INTEGER DEFAULT 0,
            overdue_days INTEGER DEFAULT 0,
            fine REAL DEFAULT 0,
            status INTEGER DEFAULT 1,  --1:在借, 2:已还, 3:逾期
            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (book_id) REFERENCES book(id)
        )
        ''')
        # 在init_db()函数中添加以下代码（放在borrow_record表之后）
        db.execute('''
        CREATE TABLE IF NOT EXISTS return_request (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrow_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            request_time TEXT NOT NULL,
            status INTEGER DEFAULT 0,  --0:待审核, 1:已通过, 2:已拒绝
            handle_time TEXT,
            handler_id INTEGER,
            FOREIGN KEY (borrow_id) REFERENCES borrow_record(id),
            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (book_id) REFERENCES book(id),
            FOREIGN KEY (handler_id) REFERENCES user(id)
        )
        ''')
        # 添加默认管理员（用户名：admin，密码：admin123，已加密）
        if not db.execute('SELECT * FROM user WHERE username = "admin"').fetchone():
            hashed_pwd = generate_password_hash('admin123')  # 加密存储密码
            db.execute(
                'INSERT INTO user (username, password, name, identity, id_card) VALUES (?, ?, ?, ?, ?)',
                ('admin', hashed_pwd, '管理员', 'admin', '000000000000000000')
            )

        # ---------------------- 图书分类 ----------------------
        if not db.execute('SELECT * FROM book_category').fetchone():
            categories = [
                (1, '计算机科学', '包含编程、算法、数据库、人工智能等图书'),
                (2, '文学小说', '包含经典小说、现代文学、外国名著等图书'),
                (3, '历史地理', '包含中外历史、地理知识、人文社科等图书'),
                (4, '科普读物', '包含自然科学、科普知识、科技前沿等图书'),
                (5, '经济管理', '包含经济学、管理学、投资理财等图书'),
                (6, '外语学习', '包含英语、日语、法语等外语学习类图书')
            ]
            db.executemany('''
                INSERT INTO book_category (id, name, description) 
                VALUES (?, ?, ?)
            ''', categories)

        # ---------------------- 带封面的图书数据 ----------------------
        if not db.execute('SELECT * FROM book').fetchone():
            books = [
                # 计算机科学（category_id=1）
                ('9787111641247', 'Python编程：从入门到实践', '埃里克·马瑟斯', '人民邮电出版社', '2020-07-01', 1, 89.0,
                 50, '/static/covers/9787111641247.jpg', 'Python入门经典，适合零基础学习者，包含实战项目'),
                ('9787115546081', 'JavaScript高级程序设计', '马特·弗里斯比', '人民邮电出版社', '2021-06-01', 1, 129.0,
                 35, '/static/covers/9787115546081.jpg', 'JS领域的经典之作，深入讲解JS核心概念和高级特性'),
                ('9787111677213', '数据库系统概念', '西尔伯沙茨', '机械工业出版社', '2020-03-01', 1, 118.0, 28,
                 '/static/covers/9787111677213.jpg', '数据库领域的经典教材，涵盖SQL、事务、索引等核心知识'),
                ('9787115588618', '人工智能：现代方法', '罗素', '人民邮电出版社', '2022-01-01', 1, 168.0, 20,
                 '/static/covers/9787115588618.jpg', 'AI领域的权威教材，全面讲解机器学习、深度学习等内容'),

                # 文学小说（category_id=2）
                ('9787530210904', '活着', '余华', '北京十月文艺出版社', '2017-09-01', 2, 39.5, 40,
                 '/static/covers/9787530210904.jpg', '中国当代文学经典，讲述一个人一生的苦难与坚韧'),
                ('9787544280607', '百年孤独', '加西亚·马尔克斯', '南海出版公司', '2017-08-01', 2, 55.0, 32,
                 '/static/covers/9787544280607.jpg', '魔幻现实主义文学的巅峰之作，讲述布恩迪亚家族的兴衰'),
                ('9787020133028', '平凡的世界', '路遥', '人民文学出版社', '2017-01-01', 2, 108.0, 38,
                 '/static/covers/9787020133028.jpg', '全景式地表现中国当代城乡社会生活的百万字长篇小说'),
                ('9787532785991', '月亮与六便士', '毛姆', '上海译文出版社', '2020-05-01', 2, 45.0, 25,
                 '/static/covers/9787532785991.jpg', '讲述一个中年画家放弃世俗生活，追求艺术理想的故事'),

                # 历史地理（category_id=3）
                ('9787508649007', '人类简史', '尤瓦尔·赫拉利', '中信出版社', '2017-02-01', 3, 68.0, 30,
                 '/static/covers/9787508649007.jpg', '从认知革命到人工智能，讲述人类如何成为地球的主宰'),
                ('9787509767251', '中国通史', '吕思勉', '社会科学文献出版社', '2019-08-01', 3, 88.0, 22,
                 '/static/covers/9787509767251.jpg', '中国史学大师吕思勉的经典著作，简明扼要的中国通史'),
                ('9787508670578', '全球通史', '斯塔夫里阿诺斯', '中信出版社', '2018-01-01', 3, 98.0, 26,
                 '/static/covers/9787508670578.jpg', '风靡全球的通史类教材，讲述人类文明的发展历程'),

                # 科普读物（category_id=4）
                ('9787535794558', '时间简史', '霍金', '湖南科学技术出版社', '2018-06-01', 4, 45.0, 33,
                 '/static/covers/9787535794558.jpg', '通俗讲解黑洞、宇宙起源等天文学知识，畅销全球'),
                ('9787535798386', '万物简史', '比尔·布莱森', '湖南科学技术出版社', '2019-03-01', 4, 68.0, 24,
                 '/static/covers/9787535798386.jpg', '从大爆炸到人类文明，用幽默的语言讲述科学发展史'),

                # 经济管理（category_id=5）
                ('9787508667357', '穷查理宝典', '彼得·考夫曼', '中信出版社', '2021-04-01', 5, 128.0, 18,
                 '/static/covers/9787508667357.jpg', '查理·芒格的智慧箴言录，涵盖投资、人生哲学'),
                ('9787111641148', '精益创业', '埃里克·莱斯', '机械工业出版社', '2020-01-01', 5, 59.0, 21,
                 '/static/covers/9787111641148.jpg', '创业领域的经典之作，讲述如何快速迭代、验证产品'),

                # 外语学习（category_id=6）
                ('9787513590235', '新概念英语3', '亚历山大', '外语教学与研究出版社', '2017-05-01', 6, 49.9, 45,
                 '/static/covers/9787513590235.jpg', '经典英语教材，提升英语听说读写能力'),
                ('9787561954355', '新标准日本语初级', '人民教育出版社', '北京语言大学出版社', '2018-08-01', 6, 79.8, 30,
                 '/static/covers/9787561954355.jpg', '日语入门经典教材，适合零基础学习者')
            ]
            db.executemany('''
                INSERT INTO book (isbn, title, author, publisher, publish_date, category_id, price, stock, cover, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', books)

        db.commit()
# 首页路由（重定向到登录页）
@app.route('/')
def index():
    return redirect(url_for('login'))


# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        identity = request.form['identity']

        db = get_db()
        user = db.execute(
            'SELECT * FROM user WHERE username = ? AND identity = ?',
            (username, identity)
        ).fetchone()

        # 1. 验证密码（使用加密验证）
        # 2. 新增：验证账号状态（status=1为正常，0为冻结）
        if user and check_password_hash(user['password'], password):
            # 新增：校验账号是否冻结
            if user['status'] == 0:
                return render_template('login.html', message='账号已被冻结，无法登录')

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['identity'] = identity
            if identity == 'admin':
                return redirect(url_for('admin_home'))
            else:
                return redirect(url_for('user_home'))
        else:
            return render_template('login.html', message='用户名或密码错误')
    return render_template('login.html')
# 读者首页
@app.route('/user/home')
def user_home():
    if 'user_id' not in session or session['identity'] != 'student':
        return redirect(url_for('login'))
    return render_template('user_home.html', username=session['username'])


# 管理员首页
@app.route('/admin/home')
def admin_home():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_home.html', username=session['username'])


# 注册页面
# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        id_card = request.form['id_card']
        phone = request.form['phone']

        # 后端校验：密码不少于6位
        if len(password) < 6:
            return render_template('register.html', message='密码长度不能少于6位')

        # 后端校验：手机号（非必填，但填了必须是11位数字）
        if phone and (len(phone) != 11 or not phone.isdigit()):
            return render_template('register.html', message='手机号必须是11位数字')

        # 密码加密处理
        hashed_pwd = generate_password_hash(password)

        db = get_db()
        # 检查用户名是否已存在
        if db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone():
            return render_template('register.html', message='用户名已存在')

        # 插入新用户（读者身份）
        db.execute(
            'INSERT INTO user (username, password, name, identity, id_card, phone) VALUES (?, ?, ?, ?, ?, ?)',
            (username, hashed_pwd, name, 'student', id_card, phone)
        )
        db.commit()
        return render_template('login.html', message='注册成功，请登录')
    return render_template('register.html')

# 图书查询页面
@app.route('/book/search')
def book_search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 新增：校验读者账号状态
    if session['identity'] == 'student':
        db = get_db()
        user = db.execute('SELECT status FROM user WHERE id = ?', (session['user_id'],)).fetchone()
        if user['status'] == 0:
            session.clear()
            return render_template('login.html', message='账号已被冻结，无法访问')

    # 获取查询参数
    title = request.args.get('title', '')
    author = request.args.get('author', '')
    isbn = request.args.get('isbn', '')
    category_id = request.args.get('category_id', '')

    # 分页参数（默认每页10条）
    page = int(request.args.get('page', 1))
    per_page = 10  # 每页显示数量

    # 构建查询条件
    query = 'SELECT b.*, bc.name as category_name FROM book b LEFT JOIN book_category bc ON b.category_id = bc.id WHERE 1=1'
    params = []
    if title:
        query += ' AND b.title LIKE ?'
        params.append(f'%{title}%')
    if author:
        query += ' AND b.author LIKE ?'
        params.append(f'%{author}%')
    if isbn:
        query += ' AND b.isbn = ?'
        params.append(isbn)
    if category_id:
        query += ' AND b.category_id = ?'
        params.append(category_id)

    # 查询符合条件的图书总数
    db = get_db()
    total_count = db.execute(query.replace('b.*, bc.name as category_name', 'COUNT(*)'), params).fetchone()[0]

    # 修复总页数计算：总页数 = 总数量 // 每页数量，若有余数则+1；若总数量为0则总页数为1
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    # 防止页码超出范围
    page = max(1, min(page, total_pages))

    # 查询当前页数据
    offset = (page - 1) * per_page
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    books = db.execute(query, params).fetchall()

    # 获取分类列表
    categories = db.execute('SELECT * FROM book_category').fetchall()

    return render_template('book_search.html',
                           books=books,
                           categories=categories,
                           page=page,
                           total_pages=total_pages)  # 传递修复后的total_pages

# 忘记密码：第一步（输入用户名验证）
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        db = get_db()
        # 检查用户是否存在
        user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
        if user:
            # 用户存在，跳转到重置密码页面（传递用户名）
            return render_template('reset_password.html', username=username)
        else:
            # 用户不存在，显示错误信息
            return render_template('forgot_password.html', message='该用户名未注册')
    # GET请求：显示输入用户名页面
    return render_template('forgot_password.html')


# 重置密码：第二步（提交新密码）
@app.route('/reset-password', methods=['POST'])
def reset_password():
    username = request.form['username']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # 验证密码一致性
    if new_password != confirm_password:
        return render_template('reset_password.html', username=username, message='两次输入的密码不一致')

    # 验证密码长度
    if len(new_password) < 6:
        return render_template('reset_password.html', username=username, message='密码长度不能少于6位')

    # 加密新密码并更新数据库
    hashed_pwd = generate_password_hash(new_password)
    db = get_db()
    db.execute('UPDATE user SET password = ? WHERE username = ?', (hashed_pwd, username))
    db.commit()

    # 重置成功，跳回登录页并提示
    return render_template('login.html', message='密码重置成功，请使用新密码登录')


# 退出登录
@app.route('/logout')
def logout():
    session.clear()  # 清空session
    return redirect(url_for('login'))


# 读者 - 我的借阅记录
@app.route('/user/my-borrows')
def my_borrows():
    if 'user_id' not in session or session['identity'] != 'student':
        return redirect(url_for('login'))
    db = get_db()
    # 查询当前用户的借阅记录（关联图书表获取图书信息）
    borrows = db.execute('''
        SELECT br.*, b.title as book_title, b.author as book_author 
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ?
        ORDER BY br.borrow_time DESC
    ''', (session['user_id'],)).fetchall()
    return render_template('my_borrows.html', borrows=borrows)


# 读者 - 借阅图书
@app.route('/book/borrow', methods=['POST'])
def borrow_book():
    if 'user_id' not in session or session['identity'] != 'student':
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    db = get_db()

    # 检查图书库存
    book = db.execute('SELECT * FROM book WHERE id = ?', (book_id,)).fetchone()
    if not book or book['stock'] <= 0:
        return redirect(url_for('book_search', message='图书库存不足，无法借阅'))

    # 检查用户是否已借阅该图书（未归还）
    existing_borrow = db.execute('''
        SELECT * FROM borrow_record 
        WHERE user_id = ? AND book_id = ? AND status = 1
    ''', (session['user_id'], book_id)).fetchone()
    if existing_borrow:
        return redirect(url_for('book_search', message='您已借阅该图书，无需重复借阅'))

    # 计算借阅时间和应还时间（默认借阅30天）
    borrow_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    due_time = (datetime.datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

    # 新增借阅记录
    db.execute('''
        INSERT INTO borrow_record (user_id, book_id, borrow_time, due_time)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], book_id, borrow_time, due_time))

    # 减少图书库存
    db.execute('UPDATE book SET stock = stock - 1 WHERE id = ?', (book_id,))
    db.commit()

    return redirect(url_for('my_borrows', message='借阅成功'))


# 读者 - 续借图书
@app.route('/book/renew', methods=['POST'])
def renew_book():
    if 'user_id' not in session or session['identity'] != 'student':
        return redirect(url_for('login'))
    borrow_id = request.form['borrow_id']
    db = get_db()

    # 检查续借条件：在借状态、续借次数<2
    borrow = db.execute('''
        SELECT br.*, b.stock FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.id = ? AND br.user_id = ? AND br.status = 1 AND br.renew_count < 2
    ''', (borrow_id, session['user_id'])).fetchone()

    if not borrow:
        return redirect(url_for('my_borrows', message='无法续借（已超续借次数或图书状态异常）'))

    # 续借：应还时间延长30天，续借次数+1
    new_due_time = (datetime.datetime.strptime(borrow['due_time'], '%Y-%m-%d %H:%M:%S') + timedelta(days=30)).strftime(
        '%Y-%m-%d %H:%M:%S')
    db.execute('''
        UPDATE borrow_record 
        SET due_time = ?, renew_count = renew_count + 1
        WHERE id = ?
    ''', (new_due_time, borrow_id))
    db.commit()

    return redirect(url_for('my_borrows', message='续借成功'))


# 管理员 - 图书管理（查看所有图书）
@app.route('/admin/book/manage')
def admin_book_manage():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    books = db.execute('SELECT * FROM book').fetchall()
    return render_template('admin_book_manage.html', books=books)


# 管理员 - 更新图书库存
@app.route('/admin/book/update-stock', methods=['POST'])
def admin_update_stock():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    stock = int(request.form['stock'])
    db = get_db()
    db.execute('UPDATE book SET stock = ? WHERE id = ?', (stock, book_id))
    db.commit()
    return redirect(url_for('admin_book_manage', message='库存更新成功'))


# 管理员 - 删除图书
@app.route('/admin/book/delete', methods=['POST'])
def admin_delete_book():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    book_id = request.form['book_id']
    db = get_db()

    # 检查图书是否有未归还的借阅记录
    borrows = db.execute('''
        SELECT * FROM borrow_record WHERE book_id = ? AND status = 1
    ''', (book_id,)).fetchall()
    if borrows:
        return redirect(url_for('admin_book_manage', message='该图书有未归还的借阅记录，无法删除'))

    # 删除图书
    db.execute('DELETE FROM book WHERE id = ?', (book_id,))
    db.commit()
    return redirect(url_for('admin_book_manage', message='图书删除成功'))


# 管理员 - 添加图书（简化版，完整功能可扩展）
@app.route('/admin/book/add', methods=['GET', 'POST'])
def admin_add_book():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    categories = db.execute('SELECT * FROM book_category').fetchall()

    if request.method == 'POST':
        isbn = request.form['isbn']
        title = request.form['title']
        author = request.form['author']
        publisher = request.form['publisher']
        publish_date = request.form['publish_date']
        category_id = request.form['category_id']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        description = request.form['description']

        # 检查ISBN是否已存在
        if db.execute('SELECT * FROM book WHERE isbn = ?', (isbn,)).fetchone():
            return render_template('admin_add_book.html', categories=categories, message='ISBN已存在')

        # 添加图书
        db.execute('''
            INSERT INTO book (isbn, title, author, publisher, publish_date, category_id, price, stock, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (isbn, title, author, publisher, publish_date, category_id, price, stock, description))
        db.commit()
        return redirect(url_for('admin_book_manage', message='图书添加成功'))

    return render_template('admin_add_book.html', categories=categories)

# 管理员 - 编辑图书（简化版）
@app.route('/admin/book/edit/<int:book_id>', methods=['GET', 'POST'])
def admin_edit_book(book_id):
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    book = db.execute('SELECT * FROM book WHERE id = ?', (book_id,)).fetchone()
    categories = db.execute('SELECT * FROM book_category').fetchall()

    if not book:
        return redirect(url_for('admin_book_manage', message='图书不存在'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        publisher = request.form['publisher']
        publish_date = request.form['publish_date']
        category_id = request.form['category_id']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        description = request.form['description']

        # 更新图书信息
        db.execute('''
            UPDATE book 
            SET title = ?, author = ?, publisher = ?, publish_date = ?, category_id = ?, price = ?, stock = ?, description = ?
            WHERE id = ?
        ''', (title, author, publisher, publish_date, category_id, price, stock, description, book_id))
        db.commit()
        return redirect(url_for('admin_book_manage', message='图书编辑成功'))

    return render_template('admin_edit_book.html', book=book, categories=categories)

# 管理员 - 借阅记录管理
@app.route('/admin/borrow/records')
def admin_borrow_records():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    records = db.execute('''
        SELECT br.*, u.username, b.title 
        FROM borrow_record br
        LEFT JOIN user u ON br.user_id = u.id
        LEFT JOIN book b ON br.book_id = b.id
        ORDER BY br.borrow_time DESC
    ''').fetchall()
    return render_template('admin_borrow_records.html', records=records)


# 管理员 - 用户管理
@app.route('/admin/user/manage')
def admin_user_manage():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    users = db.execute('SELECT * FROM user WHERE identity = "student"').fetchall()
    return render_template('admin_user_manage.html', users=users)


# 管理员 - 冻结/解冻用户账号（确保路由名称是admin_toggle_user_status）
@app.route('/admin/user/toggle-status', methods=['POST'])
def admin_toggle_user_status():
    if 'user_id' not in session or session['identity'] != 'admin':
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    db = get_db()

    # 获取当前用户状态，切换为相反状态
    user = db.execute('SELECT status FROM user WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return redirect(url_for('admin_user_manage', message='用户不存在'))

    new_status = 0 if user['status'] == 1 else 1
    db.execute('UPDATE user SET status = ? WHERE id = ?', (new_status, user_id))
    db.commit()

    return redirect(url_for('admin_user_manage'))


# 读者提交归还申请
@app.route('/request_return', methods=['POST'])
def request_return():
    if 'user_id' not in session or session.get('identity') != 'student':
        return redirect(url_for('login'))

    borrow_id = request.form.get('borrow_id')
    user_id = session['user_id']

    db = get_db()
    # 检查借阅记录是否存在且状态为在借
    borrow = db.execute('SELECT * FROM borrow_record WHERE id = ? AND user_id = ? AND status = 1',
                        (borrow_id, user_id)).fetchone()

    if not borrow:
        return "无效的借阅记录", 400

    # 检查是否已经提交过申请
    existing = db.execute('SELECT * FROM return_request WHERE borrow_id = ? AND status = 0',
                          (borrow_id,)).fetchone()

    if existing:
        return "已提交归还申请，请等待审核", 400

    # 创建归还申请
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute('''
    INSERT INTO return_request (borrow_id, user_id, book_id, request_time)
    VALUES (?, ?, ?, ?)
    ''', (borrow_id, user_id, borrow['book_id'], now))
    db.commit()

    return redirect(url_for('my_borrows'))


# 管理员查看归还申请
@app.route('/admin_return_requests')
def admin_return_requests():
    if 'user_id' not in session or session.get('identity') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    # 查询所有归还申请及关联信息
    requests = db.execute('''
    SELECT rr.*, u.username, b.title, br.borrow_time, br.due_time
    FROM return_request rr
    JOIN user u ON rr.user_id = u.id
    JOIN book b ON rr.book_id = b.id
    JOIN borrow_record br ON rr.borrow_id = br.id
    ORDER BY rr.status, rr.request_time DESC
    ''').fetchall()

    return render_template('admin_return_requests.html', requests=requests)


# 管理员处理归还申请
@app.route('/handle_return_request', methods=['POST'])
def handle_return_request():
    if 'user_id' not in session or session.get('identity') != 'admin':
        return redirect(url_for('login'))

    request_id = request.form.get('request_id')
    action = request.form.get('action')
    admin_id = session['user_id']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    req = db.execute('SELECT * FROM return_request WHERE id = ?', (request_id,)).fetchone()

    if not req:
        return "无效的申请记录", 400

    # 更新申请状态
    status = 1 if action == 'approve' else 2
    db.execute('''
    UPDATE return_request 
    SET status = ?, handle_time = ?, handler_id = ?
    WHERE id = ?
    ''', (status, now, admin_id, request_id))

    # 如果通过申请，更新借阅记录和图书库存
    if action == 'approve':
        # 更新借阅记录为已还
        db.execute('''
        UPDATE borrow_record 
        SET status = 2, return_time = ?
        WHERE id = ?
        ''', (now, req['borrow_id']))

        # 增加图书库存
        db.execute('''
        UPDATE book 
        SET stock = stock + 1 
        WHERE id = ?
        ''', (req['book_id'],))

    db.commit()
    return redirect(url_for('admin_return_requests'))

if __name__ == '__main__':
    init_db()  # 首次运行时初始化数据库（创建表和默认管理员）
    app.run(debug=False)