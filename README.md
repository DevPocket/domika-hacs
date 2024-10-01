<!-- prettier-ignore -->
![GitHub Release](https://img.shields.io/github/v/release/devpocket/domika-hacs?style=for-the-badge)
![GitHub License](https://img.shields.io/github/license/devpocket/domika-hacs?style=for-the-badge)

# Domika Integration for Home Assistant

Domika integration allows Domika mobile apps to communicate with your Home Assistance and is required for Domika mobile applications to work.

## Adding Domika

Through HACS:
- Ensure that HACS is installed.
- Open HACS, tap the dots in upper-right corner and open "Custom Repositories".
- In "Repository" field put: https://github.com/DevPocket/domika-hacs.git.
- In "Type" field select "Integration".
- Press "Add". Domika will appear below "Custom repositories" title.
- Close "Custom Repositories" window, in HACS search field type "Domika".
- Open Domika from the list, press Download.
- Restart Home Assistant.

Manually:
- Download the latest release.
- In your Home Assistant instance open "config" directory.
- If not exist, create "custom_components" directory inside your "config" directory.
- Create "domika" directory inside "custom_components" directory.
- Copy all files from "custom_components/domika" to "domika" directory you just created.
- Restart Home Assistant.

## Domika installation
- Open Home Assistant settings -> Devices & services.
- Press "Add Integration", search for Domika.
- Install Domika from the list.

- Restart Home Assistant.
Option 2 - Manual installation:
Download the latest release.
Unpack the release and copy the custom_components/webastoconnect directory into the custom_components directory of your Home Assistant installation.
Restart Home Assistant.

## Configuration
To configure Domika, open Domika integration from the list of your integrations and press "Configure". Select domains and/or entities you want to trigger critical push notifications.   


### Understanding Critical Push Notifications

Domika can send critical push notifications to any mobile device that has the Domika app installed and connected to your home. These notifications can bypass Sleep and Do Not Disturb modes, so they can be disruptive. By default, Domika doesn’t send any critical notifications — you’ll need to enable them in Domika configuration. You can choose to activate critical notifications for all binary sensors of specific types (Smoke, Moisture, CO, or Gas), or you can manually add other binary sensors. Keep in mind, all users with the Domika app installed and connected to your home will receive these critical notifications unless they’ve disabled them in their phone’s system settings.

## Troubleshooting
If you experience problems, you can enable Domika integration logs by adding "logs:" section to you logger setup in configuration.yaml. If will look like this: 

```yaml
logger:
    default: info
    logs:
        custom_components.domika: debug
        domika_ha_framework: debug
```

## Domika Documentation

- [FAQ and Contacts](https://domika.app/help/)



