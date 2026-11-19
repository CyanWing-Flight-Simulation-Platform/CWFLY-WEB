// 站内设备密钥（自研 Passkey）：
// - 私钥由浏览器 Web Crypto 生成，extractable=false，只存在 IndexedDB；
// - 服务端只保存公钥，登录时用本机私钥对一次性挑战签名。
const DB_NAME = 'cwfly_device_keys'
const STORE = 'keys'
const KEY_PREFIX = 'device2fa:'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function idbGet(key) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(key)
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

async function idbPut(key, value) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(value, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

function abToBase64(buf) {
  const bytes = new Uint8Array(buf)
  let binary = ''
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

/** 为当前账号生成并保存设备密钥，返回可上传的公钥 JWK 字符串。 */
export async function createDeviceKey(cid) {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign', 'verify'],
  )
  const publicJwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey)
  await idbPut(KEY_PREFIX + cid, keyPair.privateKey)
  return JSON.stringify(publicJwk)
}

/** 使用本机私钥签名；没有密钥时抛出 DEVICE_KEY_MISSING。 */
export async function signDeviceChallenge(cid, challenge) {
  const privateKey = await idbGet(KEY_PREFIX + cid)
  if (!privateKey) throw new Error('DEVICE_KEY_MISSING')
  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privateKey,
    new TextEncoder().encode(String(challenge)),
  )
  return abToBase64(signature)
}

export async function hasDeviceKey(cid) {
  return !!(await idbGet(KEY_PREFIX + cid))
}
