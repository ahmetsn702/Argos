# Maltego Setup & Integration Guide

This guide describes how to configure and integrate ARGOS transforms with your Maltego client.

## Configuration

To enable the Maltego transform server, configure the environment variables in your `.env` file:

```env
# Enable Maltego routes
MALTEGO_ENABLED=true

# Set the authorization API key (optional, leave blank to bypass authentication in development)
MALTEGO_API_KEY=your_secret_key_here
```

## Available Transforms

The transform server exposes the following endpoints under `/maltego`:

1. **Email to Profiles** (`argos.EmailToProfiles`)
   - Input: `maltego.EmailAddress`
   - Output: `maltego.Alias` (extracted usernames and Gravatar profiles)
2. **Username to Social Profiles** (`argos.UsernameToSocial`)
   - Input: `maltego.Alias`
   - Output: Discovered platform profiles (`maltego.Alias` with URL properties)
3. **Phone to Identity/Location** (`argos.PhoneToIdentity`)
   - Input: `maltego.PhoneNumber`
   - Output: Carrier (`maltego.Unknown`), Country (`maltego.Location`), City/Region (`maltego.Location`), Owner Name (`maltego.Person`)
4. **Domain to Infrastructure** (`argos.DomainToInfra`)
   - Input: `maltego.Domain`
   - Output: Resolved IP (`maltego.IPv4Address`), Nameservers (`maltego.Domain`), Mailservers (`maltego.Domain`)
5. **IP to Geo Location** (`argos.IpToGeo`)
   - Input: `maltego.IPv4Address`
   - Output: Full Location (`maltego.Location`), ISP (`maltego.Unknown`)
6. **Entity to Confidence Findings** (`argos.EntityToConfidence`)
   - Input: Any entity value (seed key)
   - Output: Extracted graph findings mapped to Maltego entity types with confidence scores.

## Integration with Maltego (Local/TDS Setup)

1. Open your Maltego Desktop client.
2. Go to **Transforms** -> **Transform Manager** -> **Add Transform**.
3. Configure the Transform Server URL to point to your ARGOS instance:
   ```
   http://localhost:8000/maltego/transform/{transform_name}
   ```
4. Set the HTTP Header:
   - Header: `X-Maltego-API-Key` (or `MALTEGO-API-Key`)
   - Value: The secret key configured in your `.env` file.
