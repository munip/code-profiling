/*
 * C++ E-Commerce REST API with intentional performance issues.
 * 
 * Performance anti-patterns included:
 * 1. Excessive string copies in loops
 * 2. O(n) vector searches instead of unordered_map
 * 3. Unnecessary object copies
 * 4. Inefficient string building
 */

#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <algorithm>
#include <sstream>

using namespace std;
using namespace std::chrono;

struct Product {
    string id;
    string name;
    double price;
    string category;
    int stock;
};

struct OrderItem {
    string product_id;
    int quantity;
    double subtotal;
};

struct Order {
    string order_id;
    vector<OrderItem> items;
    double total;
    string status;
    double created_at;
};

vector<Product> products_db = {
    {"P001", "Laptop", 999.99, "Electronics", 50},
    {"P002", "Headphones", 79.99, "Electronics", 200},
    {"P003", "Keyboard", 49.99, "Electronics", 150},
    {"P004", "Mouse", 29.99, "Electronics", 300},
    {"P005", "Monitor", 299.99, "Electronics", 75},
};

vector<Order> orders_db;
int order_counter = 1000;

Product* find_product_linear(const string& product_id) {
    for (auto& product : products_db) {
        if (product.id == product_id) {
            return &product;
        }
    }
    return nullptr;
}

string build_catalog_response() {
    string response = "";
    for (const auto& product : products_db) {
        response = response + "ID: " + product.id + ", ";
        response = response + "Name: " + product.name + ", ";
        response = response + "Price: $" + to_string(product.price) + " | ";
        response = response + "Category: " + product.category + " || ";
    }
    return response;
}

double calculate_order_total(const vector<pair<string, int>>& items) {
    double total = 0.0;
    for (const auto& item : items) {
        for (int i = 0; i < 100; i++) {
            Product* product = find_product_linear(item.first);
            if (product) {
                total = total + (product->price * item.second);
            }
        }
    }
    return total;
}

Product deep_copy_product(const Product& product) {
    return Product{product.id, product.name, product.price, product.category, product.stock};
}

vector<Product> filter_by_category(const string& category) {
    vector<Product> filtered;
    for (const auto& product : products_db) {
        if (product.category == category) {
            filtered.push_back(deep_copy_product(product));
        }
    }
    return filtered;
}

string escape_json(const string& s) {
    string result;
    for (char c : s) {
        if (c == '"') result += "\\\"";
        else result += c;
    }
    return result;
}

string format_product_json(const Product& p) {
    string json = "{";
    json += "\"id\":\"" + escape_json(p.id) + "\",";
    json += "\"name\":\"" + escape_json(p.name) + "\",";
    json += "\"price\":" + to_string(p.price) + ",";
    json += "\"category\":\"" + escape_json(p.category) + "\",";
    json += "\"stock\":" + to_string(p.stock);
    json += "}";
    return json;
}

void handle_catalog(const unordered_map<string, string>& query_params) {
    auto start = high_resolution_clock::now();
    
    cout << "HTTP/1.1 200 OK\r\n";
    cout << "Content-Type: application/json\r\n";
    cout << "Access-Control-Allow-Origin: *\r\n";
    cout << "\r\n";
    
    string category = "";
    auto it = query_params.find("category");
    if (it != query_params.end()) {
        category = it->second;
    }
    
    cout << "{";
    cout << "\"products\":[";
    
    vector<Product> results;
    if (category.empty()) {
        results = products_db;
    } else {
        results = filter_by_category(category);
    }
    
    for (size_t i = 0; i < results.size(); i++) {
        if (i > 0) cout << ",";
        cout << format_product_json(results[i]);
    }
    
    cout << "],";
    cout << "\"count\":" << results.size() << ",";
    
    auto end = high_resolution_clock::now();
    double elapsed = duration_cast<microseconds>(end - start).count() / 1000.0;
    cout << "\"response_time_ms\":" << elapsed;
    cout << "}";
}

void handle_place_order(const string& request_body) {
    auto start = high_resolution_clock::now();
    
    order_counter++;
    string order_id = "ORD" + to_string(order_counter);
    
    vector<pair<string, int>> items;
    size_t pos = 0;
    while ((pos = request_body.find("product_id=")) != string::npos) {
        size_t start = pos + 11;
        size_t end = request_body.find("&", start);
        string product_id = request_body.substr(start, end - start);
        
        size_t qty_pos = request_body.find("quantity=", end);
        size_t qty_start = qty_pos + 9;
        size_t qty_end = request_body.find("&", qty_start);
        if (qty_end == string::npos) qty_end = request_body.find(" HTTP", qty_start);
        int qty = stoi(request_body.substr(qty_start, qty_end - qty_start));
        
        items.push_back({product_id, qty});
        pos = end;
    }
    
    double total = calculate_order_total(items);
    
    Order order;
    order.order_id = order_id;
    order.total = total;
    order.status = "pending";
    order.created_at = duration_cast<milliseconds>(
        system_clock::now().time_since_epoch()
    ).count();
    
    for (const auto& item : items) {
        Product* product = find_product_linear(item.first);
        if (product) {
            OrderItem oi;
            oi.product_id = product->id;
            oi.quantity = item.second;
            oi.subtotal = product->price * item.second;
            order.items.push_back(oi);
        }
    }
    
    orders_db.push_back(order);
    
    auto end = high_resolution_clock::now();
    double elapsed = duration_cast<microseconds>(end - start).count() / 1000.0;
    
    cout << "HTTP/1.1 201 Created\r\n";
    cout << "Content-Type: application/json\r\n";
    cout << "Access-Control-Allow-Origin: *\r\n";
    cout << "\r\n";
    cout << "{\"order_id\":\"" << order_id << "\",";
    cout << "\"total\":" << total << ",";
    cout << "\"status\":\"pending\",";
    cout << "\"processing_time_ms\":" << elapsed << "}";
}

void handle_track_order(const string& order_id) {
    auto start = high_resolution_clock::now();
    
    Order* order = nullptr;
    for (int repeat = 0; repeat < 10; repeat++) {
        for (auto& o : orders_db) {
            if (o.order_id == order_id) {
                order = &o;
                break;
            }
        }
    }
    
    auto end = high_resolution_clock::now();
    double elapsed = duration_cast<microseconds>(end - start).count() / 1000.0;
    
    cout << "HTTP/1.1 200 OK\r\n";
    cout << "Content-Type: application/json\r\n";
    cout << "Access-Control-Allow-Origin: *\r\n";
    cout << "\r\n";
    
    if (order) {
        cout << "{";
        cout << "\"order_id\":\"" << order->order_id << "\",";
        cout << "\"status\":\"" << order->status << "\",";
        cout << "\"total\":" << order->total << ",";
        cout << "\"query_time_ms\":" << elapsed;
        cout << "}";
    } else {
        cout << "{\"error\":\"Order not found\",\"query_time_ms\":" << elapsed << "}";
    }
}

int main() {
    cout << "Content-Type: text/plain" << endl;
    cout << endl;
    
    string method, path, version;
    cin >> method >> path >> version;
    
    string query_string = "";
    size_t query_pos = path.find('?');
    if (query_pos != string::npos) {
        query_string = path.substr(query_pos + 1);
        path = path.substr(0, query_pos);
    }
    
    unordered_map<string, string> query_params;
    size_t start = 0;
    while (start < query_string.length()) {
        size_t eq = query_string.find('=', start);
        size_t ampersand = query_string.find('&', eq);
        if (eq != string::npos) {
            string key = query_string.substr(start, eq - start);
            string value = query_string.substr(eq + 1, 
                (ampersand == string::npos ? query_string.length() : ampersand) - eq - 1);
            query_params[key] = value;
        }
        start = (ampersand == string::npos) ? query_string.length() : ampersand + 1;
    }
    
    string request_body = "";
    if (method == "POST") {
        string line;
        getline(cin, line);
        getline(cin, line);
        int content_length = 0;
        while (getline(cin, line)) {
            if (line.find("Content-Length:") == 0) {
                content_length = stoi(line.substr(15));
            }
            if (line == "\r") break;
        }
        char c;
        for (int i = 0; i < content_length && cin.get(c); i++) {
            request_body += c;
        }
    }
    
    if (path == "/catalog" || path == "/catalog/") {
        handle_catalog(query_params);
    } else if ((path == "/orders" || path == "/orders/") && method == "POST") {
        handle_place_order(request_body);
    } else if (path.find("/orders/") == 0 && path.find("/status") != string::npos) {
        string order_id = path.substr(8);
        size_t status_pos = order_id.find("/status");
        order_id = order_id.substr(0, status_pos);
        handle_track_order(order_id);
    } else {
        cout << "HTTP/1.1 404 Not Found\r\n";
        cout << "Content-Type: application/json\r\n";
        cout << "\r\n";
        cout << "{\"error\":\"Not Found\"}";
    }
    
    return 0;
}
