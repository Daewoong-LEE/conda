import Foundation

struct Organization: Decodable {
    let uuid: String
}

struct UsageResponse: Decodable {
    struct WindowUsage: Decodable {
        let utilization: Double
        let resetsAt: String
        enum CodingKeys: String, CodingKey {
            case utilization
            case resetsAt = "resets_at"
        }
    }
    let fiveHour: WindowUsage?
    enum CodingKeys: String, CodingKey {
        case fiveHour = "five_hour"
    }
}
