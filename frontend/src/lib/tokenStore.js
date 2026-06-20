/**
 * Token storage.
 *
 * Security note: the JWT is held primarily in module-scope memory and mirrored
 * to sessionStorage so it survives page reloads but is wiped when the tab
 * closes. This shrinks the XSS exfiltration window compared to localStorage
 * (which persists indefinitely across tabs and devices). For a fully XSS-proof
 * setup, swap to an httpOnly cookie issued by the backend.
 */
const STORAGE_KEY = "ads_studio_token";

let memoryToken = null;

const readSession = () => {
    try {
        return sessionStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
};

const writeSession = (value) => {
    try {
        if (value === null) sessionStorage.removeItem(STORAGE_KEY);
        else sessionStorage.setItem(STORAGE_KEY, value);
    } catch {
        // sessionStorage may be unavailable (private mode); in-memory token is enough
    }
};

export const getToken = () => {
    if (memoryToken) return memoryToken;
    memoryToken = readSession();
    return memoryToken;
};

export const setToken = (token) => {
    memoryToken = token || null;
    writeSession(memoryToken);
};

export const clearToken = () => {
    memoryToken = null;
    writeSession(null);
};
