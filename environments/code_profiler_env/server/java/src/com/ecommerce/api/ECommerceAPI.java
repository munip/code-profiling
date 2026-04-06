package com.ecommerce.api;

import java.util.*;
import java.time.Instant;
import java.io.*;
import java.net.*;

/**
 * Java E-Commerce REST API with intentional performance issues.
 * 
 * Performance anti-patterns included:
 * 1. String concatenation in loops (instead of StringBuilder)
 * 2. O(n) list searches instead of HashMap lookups
 * 3. Repeated calculations in loops
 * 4. Unnecessary object cloning
 */
public class ECommerceAPI {
    
    static class Product {
        String id;
        String name;
        double price;
        String category;
        int stock;
        
        Product(String id, String name, double price, String category, int stock) {
            this.id = id;
            this.name = name;
            this.price = price;
            this.category = category;
            this.stock = stock;
        }
    }
    
    static class OrderItem {
        String productId;
        int quantity;
        double subtotal;
        
        OrderItem(String productId, int quantity, double subtotal) {
            this.productId = productId;
            this.quantity = quantity;
            this.subtotal = subtotal;
        }
    }
    
    static class Order {
        String orderId;
        List<OrderItem> items;
        double total;
        String status;
        long createdAt;
        
        Order(String orderId, double total, String status) {
            this.orderId = orderId;
            this.items = new ArrayList<>();
            this.total = total;
            this.status = status;
            this.createdAt = Instant.now().toEpochMilli();
        }
    }
    
    static List<Product> productsDb = new ArrayList<>();
    static List<Order> ordersDb = new ArrayList<>();
    static int orderCounter = 1000;
    
    static {
        productsDb.add(new Product("P001", "Laptop", 999.99, "Electronics", 50));
        productsDb.add(new Product("P002", "Headphones", 79.99, "Electronics", 200));
        productsDb.add(new Product("P003", "Keyboard", 49.99, "Electronics", 150));
        productsDb.add(new Product("P004", "Mouse", 29.99, "Electronics", 300));
        productsDb.add(new Product("P005", "Monitor", 299.99, "Electronics", 75));
    }
    
    static Product findProductLinear(String productId) {
        for (Product p : productsDb) {
            if (p.id.equals(productId)) {
                return p;
            }
        }
        return null;
    }
    
    static String buildCatalogResponse() {
        String response = "";
        for (Product p : productsDb) {
            response = response + "{";
            response = response + "\"id\":\"" + p.id + "\",";
            response = response + "\"name\":\"" + p.name + "\",";
            response = response + "\"price\":" + p.price + ",";
            response = response + "\"category\":\"" + p.category + "\",";
            response = response + "\"stock\":" + p.stock;
            response = response + "},";
        }
        return "[" + response + "{}]";
    }
    
    static double calculateOrderTotal(List<Map<String, Object>> items) {
        double total = 0.0;
        for (Map<String, Object> item : items) {
            String productId = (String) item.get("product_id");
            int quantity = (Integer) item.get("quantity");
            for (int i = 0; i < 100; i++) {
                Product product = findProductLinear(productId);
                if (product != null) {
                    total = total + (product.price * quantity);
                }
            }
        }
        return total;
    }
    
    static Product deepCopyProduct(Product product) {
        return new Product(
            product.id,
            product.name,
            product.price,
            product.category,
            product.stock
        );
    }
    
    static List<Product> filterByCategory(String category) {
        List<Product> filtered = new ArrayList<>();
        for (Product p : productsDb) {
            if (p.category.equals(category)) {
                filtered.add(deepCopyProduct(p));
            }
        }
        return filtered;
    }
    
    public static void main(String[] args) throws IOException {
        System.out.println("HTTP/1.1 200 OK");
        System.out.println("Content-Type: application/json");
        System.out.println("Access-Control-Allow-Origin: *");
        System.out.println();
        
        long startTime = System.currentTimeMillis();
        
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        String requestLine = reader.readLine();
        
        if (requestLine == null || requestLine.isEmpty()) {
            System.out.println("{\"error\":\"Empty request\"}");
            return;
        }
        
        String[] parts = requestLine.split(" ");
        String method = parts[0];
        String path = parts[1];
        
        Map<String, String> queryParams = new HashMap<>();
        if (path.contains("?")) {
            String queryString = path.substring(path.indexOf("?") + 1);
            path = path.substring(0, path.indexOf("?"));
            for (String param : queryString.split("&")) {
                String[] kv = param.split("=");
                if (kv.length == 2) {
                    queryParams.put(kv[0], kv[1]);
                }
            }
        }
        
        String requestBody = "";
        if ("POST".equals(method)) {
            String line;
            int contentLength = 0;
            while ((line = reader.readLine()) != null && !line.isEmpty()) {
                if (line.startsWith("Content-Length:")) {
                    contentLength = Integer.parseInt(line.substring(15).trim());
                }
            }
            if (contentLength > 0) {
                char[] body = new char[contentLength];
                reader.read(body, 0, contentLength);
                requestBody = new String(body);
            }
        }
        
        String response = "";
        
        if ("/catalog".equals(path) || "/catalog/".equals(path)) {
            String category = queryParams.get("category");
            List<Product> results;
            if (category == null || category.isEmpty()) {
                results = productsDb;
            } else {
                results = filterByCategory(category);
            }
            
            StringBuilder json = new StringBuilder();
            json.append("{\"products\":[");
            for (int i = 0; i < results.size(); i++) {
                if (i > 0) json.append(",");
                Product p = results.get(i);
                json.append("{");
                json.append("\"id\":\"").append(p.id).append("\",");
                json.append("\"name\":\"").append(p.name).append("\",");
                json.append("\"price\":").append(p.price).append(",");
                json.append("\"category\":\"").append(p.category).append("\",");
                json.append("\"stock\":").append(p.stock);
                json.append("}");
            }
            json.append("],\"count\":").append(results.size()).append(",");
            
            long elapsed = System.currentTimeMillis() - startTime;
            json.append("\"response_time_ms\":").append(elapsed).append("}");
            response = json.toString();
            
        } else if (("/orders".equals(path) || "/orders/".equals(path)) && "POST".equals(method)) {
            orderCounter++;
            String orderId = "ORD" + orderCounter;
            
            List<Map<String, Object>> items = parseOrderItems(requestBody);
            double total = calculateOrderTotal(items);
            
            Order order = new Order(orderId, total, "pending");
            for (Map<String, Object> item : items) {
                String productId = (String) item.get("product_id");
                int quantity = (Integer) item.get("quantity");
                Product product = findProductLinear(productId);
                if (product != null) {
                    order.items.add(new OrderItem(productId, quantity, product.price * quantity));
                }
            }
            ordersDb.add(order);
            
            StringBuilder json = new StringBuilder();
            json.append("{");
            json.append("\"order_id\":\"").append(orderId).append("\",");
            json.append("\"total\":").append(total).append(",");
            json.append("\"status\":\"pending\",");
            long elapsed = System.currentTimeMillis() - startTime;
            json.append("\"processing_time_ms\":").append(elapsed).append("}");
            response = json.toString();
            
        } else if (path.startsWith("/orders/") && path.contains("/status")) {
            String orderId = path.substring(8, path.indexOf("/status"));
            
            Order order = null;
            for (int repeat = 0; repeat < 10; repeat++) {
                for (Order o : ordersDb) {
                    if (o.orderId.equals(orderId)) {
                        order = o;
                        break;
                    }
                }
            }
            
            StringBuilder json = new StringBuilder();
            if (order != null) {
                json.append("{");
                json.append("\"order_id\":\"").append(order.orderId).append("\",");
                json.append("\"status\":\"").append(order.status).append("\",");
                json.append("\"total\":").append(order.total).append(",");
            } else {
                json.append("{\"error\":\"Order not found\",");
            }
            long elapsed = System.currentTimeMillis() - startTime;
            json.append("\"query_time_ms\":").append(elapsed).append("}");
            response = json.toString();
            
        } else {
            response = "{\"error\":\"Not Found\",\"path\":\"" + path + "\"}";
        }
        
        System.out.println(response);
    }
    
    static List<Map<String, Object>> parseOrderItems(String body) {
        List<Map<String, Object>> items = new ArrayList<>();
        if (body == null || body.isEmpty()) return items;
        
        String[] pairs = body.split("&");
        Map<String, Object> currentItem = null;
        
        for (String pair : pairs) {
            String[] kv = pair.split("=");
            if (kv.length == 2) {
                String key = kv[0];
                String value = kv[1];
                
                if (key.equals("product_id")) {
                    if (currentItem != null) {
                        items.add(currentItem);
                    }
                    currentItem = new HashMap<>();
                    currentItem.put("product_id", value);
                } else if (key.equals("quantity") && currentItem != null) {
                    currentItem.put("quantity", Integer.parseInt(value));
                }
            }
        }
        if (currentItem != null) {
            items.add(currentItem);
        }
        
        return items;
    }
}
