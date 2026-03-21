# Modbus Map: 2 Buses, 16 Devices

Фиксированная карта для шлюза `ОВЕН RS-485 -> Modbus-TCP`:

- `2` шины: `bus1`, `bus2`
- до `8` приборов на каждой шине
- всего до `16` приборов
- каждый `ТРМ138` занимает `16` holding-регистров
- каждый канал `ТРМ138` публикуется как `float32` в `2` регистра

## Служебные регистры шлюза

- `HR1` - статус связи шлюза
- `HR2` - `last_error_code`
- `HR3` - `success_counter`
- `HR4` - `timeout_counter`
- `HR5` - `protocol_error_counter`
- `HR6` - `poll_cycle_counter`

## Блок прибора

Каждый прибор занимает один блок `16` регистров:

- `+0..+1` - канал 1
- `+2..+3` - канал 2
- `+4..+5` - канал 3
- `+6..+7` - канал 4
- `+8..+9` - канал 5
- `+10..+11` - канал 6
- `+12..+13` - канал 7
- `+14..+15` - канал 8

## Карта приборов

### Bus 1

- `device 1` - `HR16..HR31`
- `device 2` - `HR32..HR47`
- `device 3` - `HR48..HR63`
- `device 4` - `HR64..HR79`
- `device 5` - `HR80..HR95`
- `device 6` - `HR96..HR111`
- `device 7` - `HR112..HR127`
- `device 8` - `HR128..HR143`

### Bus 2

- `device 1` - `HR144..HR159`
- `device 2` - `HR160..HR175`
- `device 3` - `HR176..HR191`
- `device 4` - `HR192..HR207`
- `device 5` - `HR208..HR223`
- `device 6` - `HR224..HR239`
- `device 7` - `HR240..HR255`
- `device 8` - `HR256..HR271`

## Пример адресов каналов

### Bus 1, Device 1

- канал 1 - `HR16..HR17`
- канал 2 - `HR18..HR19`
- канал 3 - `HR20..HR21`
- канал 4 - `HR22..HR23`
- канал 5 - `HR24..HR25`
- канал 6 - `HR26..HR27`
- канал 7 - `HR28..HR29`
- канал 8 - `HR30..HR31`

### Bus 1, Device 2

- канал 1 - `HR32..HR33`
- канал 2 - `HR34..HR35`
- канал 3 - `HR36..HR37`
- канал 4 - `HR38..HR39`
- канал 5 - `HR40..HR41`
- канал 6 - `HR42..HR43`
- канал 7 - `HR44..HR45`
- канал 8 - `HR46..HR47`

### Bus 2, Device 1

- канал 1 - `HR144..HR145`
- канал 2 - `HR146..HR147`
- канал 3 - `HR148..HR149`
- канал 4 - `HR150..HR151`
- канал 5 - `HR152..HR153`
- канал 6 - `HR154..HR155`
- канал 7 - `HR156..HR157`
- канал 8 - `HR158..HR159`

## Формула расчета

Если нумерация приборов на шине идет с `1`, то:

- `device_block_base = 16 + ((bus_index - 1) * 8 + (device_index - 1)) * 16`
- `channel_base = device_block_base + (channel_index - 1) * 2`

Примеры:

- `bus1/device1/channel1 -> HR16`
- `bus1/device8/channel8 -> HR142`
- `bus2/device1/channel1 -> HR144`
- `bus2/device8/channel8 -> HR270`
