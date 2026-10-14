# VPN Troubleshooting

## The VPN keeps disconnecting
- Check that you run NorthLink version 5.2 or later. Older versions drop the connection on weak Wi-Fi.
- If you are on Wi-Fi, move closer to the router or connect with a network cable.
- Switch the protocol in NorthLink settings from "Auto" to "TCP". This fixes most random disconnects.

## Error 809 or "cannot reach server"
- This usually means a firewall or hotel/airport network is blocking the VPN. Try your phone's hotspot.
- Confirm the server address is vpn.northwind.example.

## Sign-in fails
- Check that your password has not expired (passwords expire every 90 days).
- If the MFA prompt never arrives, see the MFA guide.

## Still stuck
Open a ticket on the service desk portal and attach the NorthLink log file (Help > Export logs).
