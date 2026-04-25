# Running öğrenDiem — minimal guaranteed path

This is the shortest path from a fresh clone to the app running on a
physical Android phone. Every step here was confirmed working on the
demo laptop. If you stray from it, see the troubleshooting section.

## Prerequisites

- **Node.js 20.x or 22.x** on the laptop (`node -v` to check).
- **Expo Go** installed on the phone from the Play Store / App Store.
- **A USB cable** that does data, not just power.
- The phone and laptop near each other.

That's it. No Android Studio, no Xcode, no emulator, no global npm
packages.

## One-time setup

Open a terminal in `ogrendiem-app/` and run:

```cmd
npm install
```

Three to five minutes. Installs the dependency tree from `package.json`.

If you ever see `Unable to resolve "<package>"` later, that package is
missing from `package.json`. Add it with:

```cmd
npx expo install <package>
```

(Use `npx expo install`, not `npm install` — it picks the version
matching the Expo SDK.)

## Connecting the phone — USB tethering (recommended)

Wi-Fi between phone and laptop works in theory but is fragile: routers
with client isolation, guest networks, VPNs, and Windows tagging
networks as "Public" all break it silently. **USB tethering bypasses
all of that** and is the path that worked for us.

1. Plug phone into laptop via USB.
2. On the phone: **Settings → Network & Internet → Hotspot & tethering
   → USB tethering → ON**. (iPhone: enable Personal Hotspot, then
   plug in.)
3. Windows installs a virtual NIC named "Remote NDIS based Internet
   Sharing Device" (Android) or "Apple Mobile Device Ethernet" (iPhone).
4. Find that adapter's IPv4:

   ```cmd
   ipconfig
   ```

   Look for the entry with the tether adapter's name. The IP will be
   in `192.168.42.x`, `172.20.10.x`, or `10.x.x.x` depending on phone
   model and carrier. Note the laptop-side address — call it `LAPTOP_IP`.

5. **Tag the tether connection as Private** (Settings → Network &
   Internet → click the tether connection → Network profile → Private).
   This stops Windows Firewall from blocking inbound port 8081.

## Starting Metro

In the terminal, in `ogrendiem-app/`:

```cmd
set REACT_NATIVE_PACKAGER_HOSTNAME=LAPTOP_IP
npx expo start --clear
```

Replace `LAPTOP_IP` with the actual address from `ipconfig` (no quotes,
no spaces around `=`). The `--clear` flag wipes Metro's transform cache
— always use it on the first start of a session.

The env var is critical: a Windows laptop usually has 3+ network
interfaces (Wi-Fi, USB tether, and various virtual adapters). Expo
guesses one for the QR code and often picks the wrong one. The env var
tells it which IP to advertise.

## Sanity check before scanning

Open the phone's browser and visit `http://LAPTOP_IP:8081`. If you see
a Metro/Expo response, networking is good. If it times out, the
firewall is blocking — set the tether network to Private (step 5
above) or open the port:

```powershell
New-NetFirewallRule -DisplayName "Expo Metro 8081" -Direction Inbound `
  -Protocol TCP -LocalPort 8081 -Action Allow -Profile Any
```

(PowerShell as Administrator.)

## Loading the app

1. Open Expo Go on the phone.
2. Scan the QR code shown in the terminal (or in the browser tab Expo
   opens).
3. First load takes 30–90 seconds (Metro bundles ~700 modules).
4. App opens to the Garden tab. Pick an emoji to start.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to download remote update` | Phone can't reach Metro | Check `REACT_NATIVE_PACKAGER_HOSTNAME` is the tether IP, not Wi-Fi. Browser-test `http://LAPTOP_IP:8081` from phone. |
| `Packager is not running at http://X.X.X.X:8081` | QR has wrong IP for current network | Same as above — set the env var to the right interface. |
| `Cannot find module 'babel-preset-expo'` | Half-installed `node_modules` | `rmdir /s /q node_modules` + `del /q package-lock.json` + `npm install` |
| `Unable to resolve "<package>"` from App.tsx | Package missing from `package.json` | `npx expo install <package>` |
| `Project is incompatible with this version of Expo Go` | SDK mismatch | The repo is on SDK 54. Upgrade Expo Go from the Play Store, or downgrade the project: `npx expo install expo@<your-version>` then `npx expo install --fix` |
| Bundling hangs at "X modules" forever | Stale Metro cache | Ctrl+C, restart with `npx expo start --clear` |
| Bundle starts then errors mid-way | Cancelled previous build left partial cache | Same — `--clear` |

## Why not LAN Wi-Fi?

It can work, but in practice has too many failure modes for a demo:

- Router "client isolation" silently blocks phone↔laptop traffic.
- VPNs (Tailscale, corporate, etc.) reroute through their own adapter.
- Windows tags new networks as Public and the firewall blocks 8081.
- Hyper-V / WSL / Docker virtual adapters confuse Expo's IP guess.

USB tether sidesteps all four. Latency is ~1ms, throughput saturates
USB 2.0 at ~35 MB/s — feels local.

## Why not `npx expo start --tunnel`?

Expo's tunnel uses `@expo/ngrok` under the hood. ngrok's free tier
serves a browser interstitial HTML page on first hit, which Expo Go
tries to parse as JSON manifest and fails ("Failed to download remote
update"). Tunnels also frequently time out mid-bundle. Avoid for
demos.

## Resetting app state (optional)

The app keeps an event log in AsyncStorage. To wipe all Bayes mastery
and start over:

1. Open the app → Progress tab → scroll to "Danger zone" → Reset
   everything.

Or uninstall and reinstall Expo Go.

## Stopping

`Ctrl+C` in the terminal. The phone will show "Disconnected from
Metro" — that's expected; just close Expo Go.
