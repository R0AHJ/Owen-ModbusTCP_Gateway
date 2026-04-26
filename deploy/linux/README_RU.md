# Развертывание на Linux

## Что входит

- `install.sh` - установка проекта в `/opt/owen-gateway`, создание `venv`,
  копирование конфига и регистрация `systemd`-сервиса
- `owen-gateway.service.template` - шаблон unit-файла

## Требования

- Linux с `systemd`
- `python3`
- `python3-venv`
- `rsync`
- права `sudo`

Для доступа к USB-RS485 адаптеру пользователь сервиса должен иметь доступ к
устройству `/dev/ttyUSB*` или `/dev/ttyACM*`. Обычно это решается добавлением
пользователя в группу `dialout`.

В конфиге рекомендуется указывать порт явно, без скрытых алиасов, например:

- `/dev/ttyACM0`
- `/dev/ttyACM1`
- `/dev/ttyACM2`
- `/dev/ttyACM3`

Для серверной эксплуатации лучше использовать не номер `ttyACM*`, а постоянный
alias через `udev`, например `/dev/owen-line1`. Пример правила лежит в
`deploy/linux/99-owen-serial.rules.example`.

## Быстрая установка

Из корня репозитория:

```bash
chmod +x deploy/linux/install.sh
sudo SERVICE_USER=owen ./deploy/linux/install.sh
```

По умолчанию будут использованы:

- код проекта: `/opt/owen-gateway`
- рабочий конфиг: `/etc/owen-gateway/owen_config.json`
- имя сервиса: `owen-gateway`
- группа сервиса: `dialout`

После установки проверь и при необходимости поправь поле `serial.port` в обоих
конфигах под фактический Linux-порт нужной линии.

## Постоянное имя порта через udev

Если USB-serial интерфейсы после переподключения меняют номер `ttyACM*`,
сделай собственный alias.

1. Посмотри текущие устройства:
```bash
ls -l /dev/serial/by-id
ls -l /dev/ttyACM*
```
2. Определи нужный интерфейс адаптера:
```bash
udevadm info -a -n /dev/ttyACM2
```
3. Скопируй пример правила:
```bash
sudo cp deploy/linux/99-owen-serial.rules.example /etc/udev/rules.d/99-owen-serial.rules
```
4. Подставь свои значения `idVendor`, `idProduct`, серийный номер и номер интерфейса.
5. Перезагрузи правила:
```bash
sudo udevadm control --reload
sudo udevadm trigger
```
6. Убедись, что alias появился:
```bash
ls -l /dev/owen-line1
```
7. Используй этот alias в `serial.port`, например:
```json
"port": "/dev/owen-line1"
```

## Переменные установки

Можно переопределить:

- `APP_DIR`
- `CONFIG_DIR`
- `SERVICE_NAME`
- `SERVICE_USER`
- `SERVICE_GROUP`
- `PYTHON_BIN`
- `CONFIG_SOURCE`

Пример:

```bash
sudo APP_DIR=/srv/owen-gateway \
     CONFIG_DIR=/etc/owen-gateway \
     SERVICE_NAME=owen-gateway \
     SERVICE_USER=owen \
     SERVICE_GROUP=dialout \
     CONFIG_SOURCE=$PWD/owen_config.linux.json \
     ./deploy/linux/install.sh
```

## Автозапуск

После установки сервис будет зарегистрирован и включен в автозапуск:

```bash
sudo systemctl enable owen-gateway
sudo systemctl start owen-gateway
```

Проверка:

```bash
systemctl status owen-gateway
journalctl -u owen-gateway -f
```

## Проверка конфиг-утилит

Примеры:

```bash
gate-config.sh list-serial
gate-config.sh list-config
gate-config.sh list-line --line 1
gate-config.sh show-trm138 --line 1 --base-address 96
```

`gate-config.sh` устанавливается в `/usr/local/bin` и всегда использует
`/etc/owen-gateway/owen_config.json`.

`gate-status.sh` ставится туда же и показывает:

- `systemctl status`
- доступные serial-порты и alias
- краткую сводку активного конфига
- сервисные Modbus-регистры
- последние строки `journalctl`

Также ставится `/etc/profile.d/owen-gateway.sh` с алиасами:

- `gate-config`
- `gate-menu`
- `gate-status`
- `gate-logs`
- `gate-restart`
- `gate-service`

Кроме алиасов устанавливаются и прямые команды:

- `/usr/local/bin/gate-config`
- `/usr/local/bin/gate-menu`
- `/usr/local/bin/gate-status`

## Что проверить на сервере после установки

1. Видит ли система адаптер: `ls -l /dev/ttyUSB*`
2. Имеет ли пользователь сервиса доступ к порту
3. Поднимается ли `Modbus TCP` на нужном адресе и порту
4. Читается ли `rEAd`
5. Работает ли запись `C.SP` и подтверждается ли она обратным чтением

Важно: в штатном режиме с serial-портом должен работать только один процесс
`owen-gateway`. Параллельные диагностические клиенты на том же `/dev/ttyACM*`
или `/dev/ttyUSB*` недопустимы.
