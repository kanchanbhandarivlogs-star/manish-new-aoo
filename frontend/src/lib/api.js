import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const apiClient = axios.create({
    baseURL: API,
    timeout: 180000, // 3 min, ad gen can take time
});

export const mediaUrl = (relativePath) => {
    if (!relativePath) return "";
    return `${API}/media/${relativePath}`;
};
