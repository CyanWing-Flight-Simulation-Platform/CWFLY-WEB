// 标准 WebAuthn / Passkey 客户端工具。
// 生物识别（指纹/面容/PIN）完全由浏览器与系统处理，本文件不接触任何生物特征数据。

function b64urlToBuffer(value) {
  const text = String(value || '').replace(/-/g, '+').replace(/_/g, '/')
  const padded = text + '='.repeat((4 - (text.length % 4)) % 4)
  const raw = atob(padded)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
  return bytes.buffer
}

function bufferToB64url(value) {
  const bytes = new Uint8Array(value || new ArrayBuffer(0))
  let raw = ''
  for (let i = 0; i < bytes.length; i += 1) raw += String.fromCharCode(bytes[i])
  return btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function prepareCreationOptions(options) {
  const publicKey = { ...options }
  publicKey.challenge = b64urlToBuffer(options.challenge)
  publicKey.user = { ...options.user, id: b64urlToBuffer(options.user.id) }
  if (Array.isArray(options.excludeCredentials)) {
    publicKey.excludeCredentials = options.excludeCredentials.map((item) => ({
      ...item,
      id: b64urlToBuffer(item.id),
    }))
  }
  return publicKey
}

function prepareRequestOptions(options) {
  const publicKey = { ...options }
  publicKey.challenge = b64urlToBuffer(options.challenge)
  if (Array.isArray(options.allowCredentials)) {
    publicKey.allowCredentials = options.allowCredentials.map((item) => ({
      ...item,
      id: b64urlToBuffer(item.id),
    }))
  }
  return publicKey
}

function serializeRegistrationCredential(credential) {
  const response = credential.response
  return {
    id: credential.id,
    rawId: bufferToB64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToB64url(response.clientDataJSON),
      attestationObject: bufferToB64url(response.attestationObject),
      transports: typeof response.getTransports === 'function' ? response.getTransports() : [],
    },
    clientExtensionResults: credential.getClientExtensionResults?.() || {},
  }
}

function serializeAuthenticationCredential(credential) {
  const response = credential.response
  return {
    id: credential.id,
    rawId: bufferToB64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToB64url(response.clientDataJSON),
      authenticatorData: bufferToB64url(response.authenticatorData),
      signature: bufferToB64url(response.signature),
      userHandle: response.userHandle ? bufferToB64url(response.userHandle) : null,
    },
    clientExtensionResults: credential.getClientExtensionResults?.() || {},
  }
}

export async function isPlatformPasskeyAvailable() {
  if (!window.PublicKeyCredential?.isUserVerifyingPlatformAuthenticatorAvailable) return false
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
  } catch {
    return false
  }
}

export async function createPasskey(options) {
  if (!window.PublicKeyCredential || !navigator.credentials?.create) {
    throw new Error('当前浏览器或环境不支持 Passkey')
  }
  const credential = await navigator.credentials.create({ publicKey: prepareCreationOptions(options) })
  if (!credential) throw new Error('Passkey 创建已取消')
  return serializeRegistrationCredential(credential)
}

export async function getPasskey(options) {
  if (!window.PublicKeyCredential || !navigator.credentials?.get) {
    throw new Error('当前浏览器或环境不支持 Passkey')
  }
  const credential = await navigator.credentials.get({ publicKey: prepareRequestOptions(options) })
  if (!credential) throw new Error('Passkey 登录已取消')
  return serializeAuthenticationCredential(credential)
}
