// A minimal WebSocket server (RFC 6455): the console only pushes text frames to the browser and answers ping and close.
// No dependency: the template has no `ws` package of its own. Client frames are read only to find ping/close, never interpreted.
import { createHash } from "node:crypto";
import type { IncomingMessage } from "node:http";
import type { Duplex } from "node:stream";

const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
const MAX_BUFFERED = 2 * 1024 * 1024;
const MAX_CLIENT_FRAME = 1024; // the browser sends nothing but ping/close: a larger frame closes the connection

export interface WsClient {
  send(text: string): void;
  close(): void;
  readonly open: boolean;
}

/** The Sec-WebSocket-Accept value for a key (RFC 6455, 4.2.2). */
export function acceptKey(key: string): string {
  return createHash("sha1").update(key + GUID).digest("base64");
}

/** One unmasked server text frame. */
export function textFrame(text: string): Buffer {
  const payload = Buffer.from(text, "utf8");
  const n = payload.length;
  let header: Buffer;
  if (n < 126) header = Buffer.from([0x81, n]);
  else if (n < 65536) header = Buffer.from([0x81, 126, n >> 8, n & 0xff]);
  else {
    header = Buffer.alloc(10);
    header[0] = 0x81;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(n), 2);
  }
  return Buffer.concat([header, payload]);
}

function controlFrame(opcode: number, payload: Buffer = Buffer.alloc(0)): Buffer {
  return Buffer.concat([Buffer.from([0x80 | opcode, payload.length]), payload]);
}

/**
 * Completes the upgrade of an already-checked request and returns the client. The caller has verified Host, Origin and the token:
 * this function only speaks the protocol. `onClose` runs once.
 */
export function acceptUpgrade(req: IncomingMessage, socket: Duplex, onClose: () => void): WsClient | null {
  const key = req.headers["sec-websocket-key"];
  if (typeof key !== "string" || req.headers["sec-websocket-version"] !== "13" || key.length > 64) {
    socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
    return null;
  }
  socket.write(
    `HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${acceptKey(key)}\r\n\r\n`,
  );
  let open = true;
  // a tab that vanished (laptop asleep, proxy dropped) is detected by the kernel instead of staying a ghost client
  (socket as unknown as { setKeepAlive?: (enable: boolean, delay: number) => void }).setKeepAlive?.(true, 15000);
  let buffer = Buffer.alloc(0);
  const finish = () => {
    if (!open) return;
    open = false;
    socket.destroy();
    onClose();
  };
  socket.on("close", finish);
  socket.on("error", finish);
  socket.on("data", (chunk: Buffer) => {
    buffer = Buffer.concat([buffer, chunk]);
    // read every complete client frame
    for (;;) {
      if (buffer.length < 2) return;
      const opcode = (buffer[0] as number) & 0x0f;
      const masked = ((buffer[1] as number) & 0x80) !== 0;
      let length = (buffer[1] as number) & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (buffer.length < 4) return;
        length = buffer.readUInt16BE(2);
        offset = 4;
      } else if (length === 127) {
        finish(); // 64-bit length: never sent by this page
        return;
      }
      if (!masked || length > MAX_CLIENT_FRAME) {
        finish(); // a client frame must be masked (RFC 6455, 5.1)
        return;
      }
      if (buffer.length < offset + 4 + length) return;
      const mask = buffer.subarray(offset, offset + 4);
      const payload = Buffer.from(buffer.subarray(offset + 4, offset + 4 + length));
      for (let i = 0; i < payload.length; i++) payload[i] = (payload[i] as number) ^ (mask[i % 4] as number);
      buffer = buffer.subarray(offset + 4 + length);
      if (opcode === 0x8) {
        if (open) socket.write(controlFrame(0x8));
        finish();
        return;
      }
      if (opcode === 0x9 && open) socket.write(controlFrame(0xa, payload.subarray(0, 125)));
    }
  });
  return {
    get open() {
      return open;
    },
    send(text: string) {
      if (!open) return;
      // a browser that does not read (a frozen tab) must not make the console buffer without limit
      if (socket.writableLength > MAX_BUFFERED) {
        finish();
        return;
      }
      socket.write(textFrame(text));
    },
    close() {
      if (open) socket.write(controlFrame(0x8));
      finish();
    },
  };
}
