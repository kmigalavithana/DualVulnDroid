/// Mirrors the real `user` object in /login and /register's response -
/// every field here is exactly what the backend returned, nothing added.
class UserModel {
  final int id;
  final String email;
  final String? name;

  const UserModel({required this.id, required this.email, this.name});

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as int,
      email: json['email'] as String,
      name: json['name'] as String?,
    );
  }

  String get displayName => (name != null && name!.trim().isNotEmpty) ? name! : email;
}
