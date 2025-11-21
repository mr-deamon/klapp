# KLAPP Home Assistant Integration

This custom integration allows you to monitor KLAPP messages in Home Assistant.

## Installation

1. Copy the `klapp` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "KLAPP" and follow the configuration steps

## Features

- **Sensor**: Shows the number of unread messages with attributes containing message details
- **Service**: `klapp.mark_as_read` - Mark messages as read by providing the message ID

## Configuration

Configure via the UI:
- Email: Your KLAPP account email
- Password: Your KLAPP account password

The integration polls for new messages every 5 minutes by default.

## Sensors

- `sensor.klapp_unread_messages`: Number of unread messages
  - Attributes include latest message subject, body, ID, and a list of all unread messages

## Services

### `klapp.mark_as_read`

Mark a KLAPP message as read.

**Parameters:**
- `message_id` (required): The ID of the message to mark as read

**Example:**
```yaml
service: klapp.mark_as_read
data:
  message_id: "{{ state_attr('sensor.klapp_unread_messages', 'latest_id') }}"
```

## Example Automation

```yaml
automation:
  - alias: "Notify on new KLAPP message"
    trigger:
      - platform: state
        entity_id: sensor.klapp_unread_messages
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New KLAPP Message"
          message: "{{ state_attr('sensor.klapp_unread_messages', 'latest_subject') }}"
```
