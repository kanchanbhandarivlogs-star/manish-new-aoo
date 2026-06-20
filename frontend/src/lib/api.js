import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// 3-minute timeout — ad generation (Nano Banana + GPT) can occasionally run long
const API_TIMEOUT_MS = 180_000;

export const apiClient = axios.create({
    baseURL: API,
    timeout: API_TIMEOUT_MS,
});

export const mediaUrl = (relativePath) => {
    if (!relativePath) return "";
    return `${API}/media/${relativePath}`;
};
