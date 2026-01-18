# BANK P2P NODE

## Setup

### Database setup

Create database, user and login for it.  
Database structure is simple and looks like that:
```sql
create database bank_db;

use bank_db;

create table accounts(
	id int primary key auto_increment not null unique,
    balance int not null default 0
);
```

### Run the program

## Lib code

Code used for project:

### 1. Data provider

From [my project](https://github.com/45676f725a75796576/data_provider).